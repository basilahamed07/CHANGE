"""M11 DailyRun tests — ordering, persistence, recovery, target accounting."""
import json

import pytest

from app.daily_run import STAGES, DailyRun, DailyRunReport


class FakeDB:
    """Minimal DB double for orchestration tests."""

    def __init__(self, packages_on_date=3):
        self.saved = {}
        self.packages = packages_on_date

    async def save_daily_run_state(self, run_date, state):
        self.saved[run_date] = json.dumps(state)

    async def get_daily_run_state(self, run_date):
        raw = self.saved.get(run_date)
        return json.loads(raw) if raw else None

    async def count_packages_created_on(self, run_date):
        return self.packages


def make_impl(name, detail=None, fail=False):
    async def impl(report, stage):
        if fail:
            raise RuntimeError(f"{name} exploded")
        return detail or {}
    return impl


@pytest.mark.asyncio
async def test_daily_run_route_wires_all_ten_stages(client, app, monkeypatch):
    """Regression for S6: the API route must not pass most stages as None."""
    class _Registry:
        def enabled_countries(self):
            return [type("_Country", (), {"code": "SG"})()]

    async def _ok_resume(request):
        return None

    async def _discover(*args, **kwargs):
        return {"new_jobs": 0, "pass_budget": 1, "budget_exhausted": False}

    async def _classify(db, ai_client=None):
        return 0

    async def _eligibility(db, registry=None, force=False, limit=2000):
        return 0

    async def _ai_state_for(request):
        return {"client": None, "matcher": None, "tailor": None,
                "evidence_store": None, "evidence_checker": None}

    async def _hybrid_state(request):
        return type("_State", (), {})()

    async def _hybrid(app_state, db, limit=2000):
        return {"scored": 0, "total": 0, "engine": "hybrid-m6"}

    monkeypatch.setattr("app.search_gate.require_resume_for_search", _ok_resume)
    monkeypatch.setattr("app.discovery.run_discovery_cycle", _discover)
    monkeypatch.setattr("app.scheduler.run_location_classification", _classify)
    monkeypatch.setattr("app.scheduler.run_eligibility_pass", _eligibility)
    monkeypatch.setattr("app.routers.matching._hybrid_state", _hybrid_state)
    monkeypatch.setattr("app.matching_service.score_all_unscored", _hybrid)
    app.state.country_registry = _Registry()
    app.state.ai_state_for = _ai_state_for

    r = await client.post("/api/daily-run/run")

    assert r.status_code == 200
    stages = r.json()["stages"]
    assert [s["name"] for s in stages] == STAGES
    assert all(s["status"] == "done" for s in stages)
    assert not any(s["detail"].get("reason") == "not_implemented" for s in stages)


@pytest.mark.asyncio
async def test_all_stages_run_in_order():
    order = []

    def impl_for(name):
        async def impl(report, stage):
            order.append(name)
            return {}
        return impl

    db = FakeDB()
    runner = DailyRun(db, daily_target=3)
    report = await runner.run({n: impl_for(n) for n in STAGES}, run_date="2026-09-23")
    assert order == STAGES
    assert all(s.status == "done" for s in report.stages)


@pytest.mark.asyncio
async def test_missing_stage_skipped_not_failed():
    db = FakeDB()
    runner = DailyRun(db, daily_target=3)
    report = await runner.run({}, run_date="2026-09-23")
    skipped = [s for s in report.stages if s.status == "skipped"]
    assert len(skipped) == len(STAGES)


@pytest.mark.asyncio
async def test_stage_failure_recorded_and_run_continues():
    db = FakeDB()
    runner = DailyRun(db, daily_target=3)
    report = await runner.run({
        "score": make_impl("score", fail=True),
        "select": make_impl("select"),
    }, run_date="2026-09-23")
    failed = [s for s in report.stages if s.name == "score"]
    assert failed[0].status == "failed" and "exploded" in failed[0].detail["error"]
    assert [s for s in report.stages if s.name == "select"][0].status == "done"


@pytest.mark.asyncio
async def test_state_persisted_and_recovered():
    db = FakeDB()
    runner = DailyRun(db, daily_target=3)
    await runner.run({"score": make_impl("score")}, run_date="2026-09-23")
    assert "2026-09-23" in db.saved

    # New runner resumes: completed stages are NOT re-run.
    calls = []

    async def spy(report, stage):
        calls.append(stage.name)
        return {}

    runner2 = DailyRun(db, daily_target=3)
    report = await runner2.run({"score": spy}, run_date="2026-09-23")
    assert calls == []                      # already done in the prior run
    assert report.recovered is True


@pytest.mark.asyncio
async def test_crashed_running_stage_reruns_with_reason():
    db = FakeDB()
    # Simulate a crash: state saved with stage 'score' left 'running'
    state = {"run_date": "2026-09-23", "daily_target": 3, "packages_created": 0,
             "stages": [{"name": "score", "status": "running", "detail": {}}]}
    db.saved["2026-09-23"] = json.dumps(state)

    calls = []

    async def score_impl(report, stage):
        calls.append(stage.name)
        return {}

    runner = DailyRun(db, daily_target=3)
    report = await runner.run({"score": score_impl}, run_date="2026-09-23")
    assert calls == ["score"]               # re-ran
    assert report.stages[0].status == "done"


@pytest.mark.asyncio
async def test_target_met_vs_shortfall():
    db_met = FakeDB(packages_on_date=5)
    report = await DailyRun(db_met, daily_target=5).run({}, run_date="2026-09-23")
    assert report.to_dict()["target_met"] is True
    assert report.to_dict()["shortfall_reasons"] == ["TARGET_REACHED"]

    db_short = FakeDB(packages_on_date=1)
    report2 = await DailyRun(db_short, daily_target=5).run({}, run_date="2026-09-24")
    d = report2.to_dict()
    assert d["target_met"] is False
    assert "TARGET_REACHED" not in d["shortfall_reasons"]
    assert len(d["shortfall_reasons"]) >= 1


@pytest.mark.asyncio
async def test_shortfall_reasons_are_machine_readable():
    db = FakeDB(packages_on_date=0)
    runner = DailyRun(db, daily_target=5)
    report = await runner.run({
        "score": make_impl("score", {"shortfall_reasons": ["AI_QUOTA_EXHAUSTED"]}),
    }, run_date="2026-09-23")
    assert "AI_QUOTA_EXHAUSTED" in report.shortfall_reasons()
