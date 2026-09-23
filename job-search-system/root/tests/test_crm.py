"""M10 CRM engine tests — transitions, follow-up cadence, approval matrix."""
from datetime import datetime, timedelta, timezone

import pytest

from app.crm import (
    ALL_STATUSES,
    FOLLOW_UP_STOP_STATUSES,
    TERMINAL_STATUSES,
    approval_required,
    check_transition,
    compute_follow_up,
    default_cadence,
    should_follow_up,
)

NOW = datetime.now(timezone.utc)


# ------------------------------------------------- status transition validity

def test_forward_pipeline_transitions_valid():
    assert check_transition("interested", "prepared").ok
    assert check_transition("prepared", "applied").ok
    assert check_transition("applied", "interviewing").ok
    assert check_transition("interviewing", "offered").ok


def test_off_platform_skips_allowed():
    """Applications happen off-platform: the UI's own "Mark applied" button
    must work from interested, and interviews can arrive after an external
    application (prepared -> interviewing)."""
    assert check_transition("interested", "applied").ok
    assert check_transition("prepared", "interviewing").ok


def test_cannot_jump_straight_to_offer():
    """No offer without ever applying/interviewing — keeps the funnel honest."""
    r = check_transition("interested", "offered")
    assert not r.ok and "not allowed" in r.reason
    r = check_transition("prepared", "offered")
    assert not r.ok


def test_corrections_backward_allowed():
    assert check_transition("applied", "prepared").ok
    assert check_transition("interviewing", "applied").ok
    assert check_transition("offered", "interviewing").ok


def test_terminal_states_have_no_forward_moves():
    for s in ("rejected", "withdrawn", "closed"):
        r = check_transition(s, "applied", actor="engine")
        assert not r.ok
        r = check_transition(s, "interviewing", actor="human")
        assert not r.ok


def test_ghosted_reengagement_allowed():
    r = check_transition("ghosted", "applied")
    assert r.ok


def test_engine_cannot_transition_terminal():
    r = check_transition("rejected", "applied", actor="engine")
    assert not r.ok and "terminal" in r.reason


def test_unknown_statuses_rejected():
    assert not check_transition("frobnicating", "applied").ok
    assert not check_transition("applied", "frobnicating").ok


def test_same_status_is_noop():
    r = check_transition("applied", "applied")
    assert not r.ok and "unchanged" in r.reason


def test_every_status_has_transition_entry():
    for s in ALL_STATUSES + ["accepted", "declined"]:
        assert s in check_transition.__globals__["VALID_TRANSITIONS"]


# ------------------------------------------------------- follow-up cadence

def test_cadence_applies_to_active_states_only():
    assert should_follow_up("applied")
    assert should_follow_up("prepared")
    assert not should_follow_up("interested")
    for s in TERMINAL_STATUSES:
        assert not should_follow_up(s)


def test_applied_due_after_7_days():
    plan = compute_follow_up(1, "applied", NOW - timedelta(days=8), now=NOW)
    assert plan.due and plan.days_overdue >= 1


def test_applied_not_due_within_7_days():
    plan = compute_follow_up(1, "applied", NOW - timedelta(days=3), now=NOW)
    assert not plan.due


def test_pending_reminder_blocks_duplicate():
    plan = compute_follow_up(1, "applied", NOW - timedelta(days=30),
                             pending_reminder=True, now=NOW)
    assert not plan.due and plan.stop_rule == "reminder_pending"


def test_terminal_status_never_follows_up():
    for s in ("rejected", "withdrawn", "closed", "ghosted", "offered"):
        plan = compute_follow_up(1, s, NOW - timedelta(days=365), now=NOW)
        assert not plan.due


def test_no_touch_is_due_immediately():
    plan = compute_follow_up(1, "applied", None, now=NOW)
    assert plan.due


def test_cadence_days_per_status():
    assert default_cadence("prepared") == 3
    assert default_cadence("applied") == 7
    assert default_cadence("interviewing") == 5


def test_stop_statuses_include_offer():
    assert "offered" in FOLLOW_UP_STOP_STATUSES
    assert "rejected" in FOLLOW_UP_STOP_STATUSES


# ---------------------------------------------------------- approval matrix

def test_approval_matrix_risk_levels():
    assert approval_required("scrape") == "auto"
    assert approval_required("package_build") == "review"
    assert approval_required("outreach_send") == "explicit"
    assert approval_required("allow_send") == "explicit"
    assert approval_required("unknown_action") == "explicit"
