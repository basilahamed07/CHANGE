"""M11 — DailyRun orchestration.

One function runs the whole daily pipeline in dependency order:
    discover → normalize/dedupe (ingest) → classify → eligibility →
    AI score → hybrid score (leftovers) → select top jobs →
    research contacts → build packages → draft outreach → digest

Design rules honoured here:
- daily_target counts NEW QUALIFYING PACKAGES (Golden Rule 4) — not scrapes,
  not jobs found, not scores computed.
- Never lowers the bar: shortfall is reported with machine-readable reasons.
- Run recovery: state is persisted after every stage (daily_runs table +
  daily_run_state JSON) so an interrupted run resumes where it stopped
  instead of double-running paid stages.
- Human approval gates respected: packages are born ready_for_review and
  outreach is DRAFT-ONLY — the daily run never sends anything.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Stage order = dependency order. A stage is skipped iff its inputs were
# produced in a previous (persisted) run and nothing new is pending.
STAGES = [
    "discover",       # scrape/adapter cycle (budget-capped)
    "classify",       # location classification (rule-based + LLM ambiguous)
    "eligibility",    # deterministic gate chain on new/changed jobs
    "score",          # AI score of eligible jobs (circuit-broken, never blocks)
    "hybrid_score",   # free deterministic scoring of whatever AI could not
    "select",         # pick top eligible+scored jobs toward today's target
    "research",       # company + contact research (cache-first)
    "packages",       # evidence-gated package build for selected jobs
    "outreach",       # DRAFT-ONLY outreach for packages with contacts
    "digest",         # daily digest summary notification
]

# Machine-readable shortfall reasons (never lower the bar).
SHORTFALL_REASONS = {
    "NO_AI_PROVIDER": "no AI provider configured — scoring skipped",
    "AI_QUOTA_EXHAUSTED": "AI provider rate-limited/quota exhausted mid-run",
    "NO_ELIGIBLE_JOBS": "eligibility gate produced no candidates",
    "ALL_SCORED_BELOW_CUTOFF": "every candidate scored below the cutoff",
    "SOURCES_EXHAUSTED": "all sources ran with no new listings",
    "RATE_LIMITED": "scraper rate limits stopped discovery early",
    "EVIDENCE_GATE": "packages refused by the evidence checker",
    "PACKAGE_ERROR": "package generation failed",
    "RUN_INTERRUPTED": "previous run crashed mid-stage (recovered)",
    "TARGET_REACHED": "daily target met",
}


@dataclass
class StageResult:
    name: str
    status: str = "pending"          # pending|running|done|skipped|failed
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass
class DailyRunReport:
    run_date: str
    daily_target: int
    stages: list[StageResult] = field(default_factory=list)
    packages_created: int = 0
    recovered: bool = False

    def stage(self, name: str) -> StageResult:
        for s in self.stages:
            if s.name == name:
                return s
        s = StageResult(name)
        self.stages.append(s)
        return s

    def shortfall_reasons(self) -> list[str]:
        """Machine-readable reasons why target wasn't met (deduped, ordered)."""
        reasons: list[str] = []
        if self.packages_created >= self.daily_target:
            return ["TARGET_REACHED"]
        for s in self.stages:
            for r in s.detail.get("shortfall_reasons", []):
                if r not in reasons:
                    reasons.append(r)
        if not reasons:
            reasons.append("NO_ELIGIBLE_JOBS")
        return reasons

    def to_dict(self) -> dict:
        return {
            "run_date": self.run_date,
            "daily_target": self.daily_target,
            "packages_created": self.packages_created,
            "target_met": self.packages_created >= self.daily_target,
            "shortfall_reasons": self.shortfall_reasons(),
            "recovered": self.recovered,
            "stages": [s.to_dict() for s in self.stages],
        }


class DailyRun:
    """Orchestrates one day's pipeline with persisted, resumable state."""

    def __init__(self, db, daily_target: int = 5, score_cutoff: int = 60):
        self.db = db
        self.daily_target = daily_target
        self.score_cutoff = score_cutoff
        self.report: DailyRunReport | None = None

    # ---------------------------------------------------------- persistence

    async def _persist(self) -> None:
        await self.db.save_daily_run_state(self.report.run_date, self.report.to_dict())

    async def _load_or_create(self, run_date: str) -> DailyRunReport:
        saved = await self.db.get_daily_run_state(run_date)
        if saved:
            report = DailyRunReport(
                run_date=saved["run_date"],
                daily_target=saved["daily_target"],
                packages_created=saved["packages_created"],
                recovered=True,
            )
            for s in saved.get("stages", []):
                report.stages.append(StageResult(**s))
            # A crashed stage re-runs; 'running' counts as incomplete.
            for s in report.stages:
                if s.status == "running":
                    s.status = "pending"
                    s.detail["shortfall_reasons"] = ["RUN_INTERRUPTED"]
            return report
        return DailyRunReport(run_date=run_date, daily_target=self.daily_target)

    # -------------------------------------------------------------- running

    async def run(self, stage_impls: dict[str, Callable[..., Awaitable[dict]]],
                  run_date: str | None = None) -> DailyRunReport:
        """Execute the pipeline. stage_impls maps stage name → async callable
        returning a detail dict. Callables receive (report, stage) and do
        their own DB work; orchestration owns order, persistence, targets."""
        now = datetime.now(timezone.utc)
        run_date = run_date or now.strftime("%Y-%m-%d")
        self.report = await self._load_or_create(run_date)
        recovered = self.report.recovered

        for name in STAGES:
            impl = stage_impls.get(name)
            stage = self.report.stage(name)
            if stage.status == "done":
                continue                     # already completed in a prior run
            if impl is None:
                stage.status = "skipped"
                stage.detail["reason"] = "not_implemented"
                continue
            stage.status = "running"
            await self._persist()            # crash marker BEFORE work
            try:
                detail = await impl(self.report, stage) or {}
                stage.detail.update(detail)
                stage.status = "done"
            except Exception as e:           # noqa: BLE001 — record, keep going
                logger.exception("DailyRun stage '%s' failed", name)
                stage.status = "failed"
                stage.detail["error"] = str(e)
            await self._persist()

        await self._finish(run_date)
        self.report.recovered = recovered
        return self.report

    async def _finish(self, run_date: str) -> None:
        """Count today's NEW qualifying packages and close the report."""
        count = await self.db.count_packages_created_on(run_date)
        self.report.packages_created = count
        met = count >= self.report.daily_target
        stage = self.report.stage("digest")
        stage.detail["target_met"] = met
        if not met:
            stage.detail["shortfall_reasons"] = self.report.shortfall_reasons()


async def select_candidates(db, cutoff: int, limit: int) -> dict:
    """Deterministic selection: eligible + scored above cutoff, not yet packaged,
    best score first. Returns counts + shortfall reasons for the run report."""
    rows = await db.get_top_unpackaged_jobs(cutoff=cutoff, limit=limit)
    return {"selected": len(rows), "job_ids": [r["job_id"] for r in rows]}
