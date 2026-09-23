"""M10 — CRM status engine + follow-up cadence.

Deterministic by Golden Rule 3: transition validity, stop rules and cadence
math are pure Python. No LLM anywhere in this module.

Status model (Phase 23 pipeline):
    interested → prepared → applied → interviewing → offered
                                            ↘ rejected / withdrawn / closed

Terminal states (Phase 23): rejected, withdrawn, closed, ghosted.
A terminal application never receives new follow-up reminders and the
follow-up engine skips it entirely.

Event history is append-only: app_events rows are never updated or deleted.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# --------------------------------------------------------------- statuses

# Ordered pipeline — index order defines forward progression.
PIPELINE_STATUSES = [
    "interested",
    "prepared",
    "applied",
    "interviewing",
    "offered",
]

# Off-pipeline states (set any time from any non-terminal state).
SIDE_STATUSES = ["rejected", "withdrawn", "closed", "ghosted"]

ALL_STATUSES = PIPELINE_STATUSES + SIDE_STATUSES

# Once in a terminal state, only reversal to a pipeline state by explicit
# human action is possible (same transition table governs it — see below).
TERMINAL_STATUSES = {"rejected", "withdrawn", "closed", "ghosted"}

# Who may perform a transition: "human" = explicit user action via API,
# "engine" = the follow-up/daily pipeline acting on config cadence.
#
# Forward skips WITHIN the pipeline are allowed because real applications
# happen off-platform: a user may apply straight from 'interested' (the UI's
# own "Mark applied" button does this) or land an interview after applying
# externally. What stays forbidden:
#   - jumping to 'offered' without ever applying/interviewing (keeps the
#     funnel meaningful),
#   - resurrecting a terminal state,
#   - the engine (never the human) moving a terminal state.
VALID_TRANSITIONS: dict[str, set[str]] = {
    "interested": {"prepared", "applied", "rejected", "withdrawn", "closed"},
    "prepared": {"interested", "applied", "interviewing", "rejected", "withdrawn", "closed"},
    "applied": {"prepared", "interviewing", "offered", "rejected", "withdrawn", "closed", "ghosted"},
    "interviewing": {"applied", "offered", "rejected", "withdrawn", "closed", "ghosted"},
    "offered": {"interviewing", "accepted", "declined", "withdrawn", "closed"},
    # Terminal states: nothing moves forward from here — not even by a human
    # mis-click (prevents accidental resurrection and keeps analytics honest).
    "rejected": set(),
    "withdrawn": set(),
    "closed": set(),
    "ghosted": {"applied", "rejected", "withdrawn", "closed"},  # re-engage or close
    "accepted": set(),
    "declined": {"interviewing"},
}

# Transitions that mark the application finished (stop follow-ups).
FOLLOW_UP_STOP_STATUSES = TERMINAL_STATUSES | {"offered", "accepted"}


@dataclass
class TransitionResult:
    """Machine-readable outcome of a proposed transition."""
    ok: bool
    from_status: str
    to_status: str
    reason: str = ""
    actor: str = "human"
    event_type: str = "status_change"


def check_transition(from_status: str, to_status: str, actor: str = "human") -> TransitionResult:
    """Validate a status transition. Pure function — no DB, no AI."""
    if from_status not in VALID_TRANSITIONS:
        return TransitionResult(False, from_status, to_status,
                                f"unknown current status '{from_status}'", actor)
    if to_status not in ALL_STATUSES + ["accepted", "declined"]:
        return TransitionResult(False, from_status, to_status,
                                f"unknown target status '{to_status}'", actor)
    if from_status == to_status:
        return TransitionResult(False, from_status, to_status,
                                "status unchanged", actor)
    allowed = VALID_TRANSITIONS[from_status]
    if to_status not in allowed:
        return TransitionResult(
            False, from_status, to_status,
            f"'{from_status}' → '{to_status}' not allowed; "
            f"valid next: {sorted(allowed) or 'none (terminal)'}",
            actor,
        )
    # Engine may never resurrect a terminal state.
    if actor == "engine" and from_status in TERMINAL_STATUSES:
        return TransitionResult(False, from_status, to_status,
                                "terminal state: engine cannot transition", actor)
    return TransitionResult(True, from_status, to_status, "ok", actor)


def should_follow_up(status: str) -> bool:
    """Follow-up cadence applies only to active pipeline states."""
    return status in ("prepared", "applied", "interviewing")


# --------------------------------------------------------------- cadence

@dataclass
class FollowUpPlan:
    """Computed follow-up decision for one application."""
    job_id: int
    status: str
    due: bool
    reason: str
    next_remind_at: str | None = None
    days_overdue: int = 0
    stop_rule: str = ""


def default_cadence(status: str) -> int:
    """Days after last touch before a follow-up is due, per status."""
    return {
        "prepared": 3,   # nudge to apply
        "applied": 7,    # classic recruiter follow-up window
        "interviewing": 5,
    }.get(status, 7)


def compute_follow_up(job_id: int, status: str, last_touch: datetime | None,
                      pending_reminder: bool = False,
                      now: datetime | None = None) -> FollowUpPlan:
    """Deterministic follow-up decision for one application.

    Stop rules (Phase 23):
      - terminal or post-offer statuses never follow up
      - one pending reminder at a time
      - due only after the cadence window past the last touch
    """
    now = now or datetime.now(timezone.utc)

    if not should_follow_up(status):
        stop = "terminal" if status in FOLLOW_UP_STOP_STATUSES else "not_in_cadence"
        return FollowUpPlan(job_id, status, False,
                            f"no follow-up for status '{status}'", stop_rule=stop)

    if pending_reminder:
        return FollowUpPlan(job_id, status, False,
                            "pending reminder already exists", stop_rule="reminder_pending")

    if last_touch is None:
        return FollowUpPlan(job_id, status, True, "no recorded touch — due now",
                            next_remind_at=now.isoformat())

    days = default_cadence(status)
    due_at = last_touch + timedelta(days=days)
    if now >= due_at:
        overdue = (now - due_at).days
        return FollowUpPlan(job_id, status, True,
                            f"{days}d cadence elapsed", next_remind_at=now.isoformat(),
                            days_overdue=overdue)
    return FollowUpPlan(job_id, status, False,
                        f"next follow-up in {(due_at - now).days}d",
                        next_remind_at=due_at.isoformat())


# --------------------------------------------------- approval matrix (P34)

# Low-risk bulk-approvable actions vs actions needing per-item review.
APPROVAL_MATRIX = {
    "scrape": {"risk": "low", "approval": "auto"},
    "score": {"risk": "low", "approval": "auto"},
    "package_build": {"risk": "medium", "approval": "review"},   # evidence-gated
    "package_send": {"risk": "high", "approval": "explicit"},    # never bulk
    "outreach_draft": {"risk": "medium", "approval": "review"},  # draft-only
    "outreach_send": {"risk": "high", "approval": "explicit"},   # requires ALLOW_SEND
    "status_change": {"risk": "low", "approval": "auto"},
    "bulk_status_change": {"risk": "medium", "approval": "review"},
    "country_strategy": {"risk": "medium", "approval": "review"},
    "allow_send": {"risk": "high", "approval": "explicit"},
}


def approval_required(action: str) -> str:
    """Return 'auto' | 'review' | 'explicit' for an action. Unknown → explicit."""
    return APPROVAL_MATRIX.get(action, {"approval": "explicit"})["approval"]
