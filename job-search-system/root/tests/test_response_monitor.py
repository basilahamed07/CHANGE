"""M12 response monitor tests — classifier, REVIEW routing, feedback recs."""
from app.response_monitor import (
    CONFIDENCE_FLOOR,
    classify_email,
    recommend,
    response_correlation,
)

# ------------------------------------------------------------- classifier

def test_interview_invite():
    c = classify_email(subject="Interview invitation",
                       body="We'd like to schedule a call Thursday, here's a calendar link")
    assert c.label == "interview_invite" and not c.review


def test_offer_detected():
    c = classify_email(subject="", body="We are pleased to offer you the position — "
                                        "see attached offer letter")
    assert c.label == "offer" and c.confidence >= CONFIDENCE_FLOOR


def test_rejection_detected():
    c = classify_email(subject="Your application",
                       body="Unfortunately, we have decided not to move forward")
    assert c.label == "rejection" and not c.review


def test_availability_request():
    c = classify_email(subject="", body="What time works for a quick call this week?")
    assert c.label == "availability_request"


def test_more_info_request():
    c = classify_email(subject="", body="Could you share your portfolio and notice period?")
    assert c.label == "more_info_request"


def test_out_of_office():
    c = classify_email(subject="OOO", body="I am out of the office until Monday with "
                                           "limited email access until then")
    assert c.label == "out_of_office"


def test_auto_ack():
    c = classify_email(subject="Application received",
                       body="Thank you for your application. This is an automatic reply")
    assert c.label == "auto_ack" and not c.review


def test_no_reply_sender_is_auto_ack():
    c = classify_email(subject="Application update", body="Your status has changed",
                       sender="noreply@bigcorp.com")
    assert c.label == "auto_ack" and c.confidence >= 0.9


def test_unmatched_goes_to_review():
    c = classify_email(subject="hi", body="Just checking in about the role")
    assert c.label == "review" and c.review is True


def test_low_confidence_routes_to_review_never_silent():
    """Ambiguous text with a weak match → REVIEW, never a silent guess."""
    c = classify_email(subject="Quick question",
                       body="What is your availability for a coffee chat sometime?")
    if c.confidence < CONFIDENCE_FLOOR:
        assert c.label == "review" and c.review
    else:
        assert c.label in ("availability_request", "review")


def test_interview_beats_auto_ack_for_no_reply():
    c = classify_email(subject="Invite", body="Please join the interview via zoom",
                       sender="noreply@bigcorp.com")
    assert c.label == "interview_invite"


# ---------------------------------------------------------- feedback loop

def test_no_recommendations_below_min_sample():
    r = recommend({}, funnel={"applied": 3, "rejected": 2, "interviewing": 0},
                  sources=[], min_sample=20)
    assert r["review_required"] is True
    assert r["auto_rewrite_performed"] is False
    assert any(rec["area"] == "sample_size" for rec in r["recommendations"])


def test_high_rejection_rate_flags_targeting():
    # rejection share over applied+rejected = 28/30 ≈ 0.93 > 0.8 → flags
    r = recommend({}, funnel={"applied": 30, "rejected": 28, "interviewing": 0},
                  sources=[], min_sample=20)
    assert any(rec["area"] == "targeting" for rec in r["recommendations"])


def test_strong_conversion_suggests_raising_target():
    # outcome sample = interviewing+offered+rejected = 8+2+3 = 13 ≥ 10 (min_sample)
    r = recommend({}, funnel={"applied": 30, "rejected": 3,
                              "interviewing": 8, "offered": 2},
                  sources=[], min_sample=10)
    assert any("raising daily target" in rec["suggestion"]
               for rec in r["recommendations"])


def test_source_spread_recommendation():
    sources = [
        {"source": "good", "jobs": 25, "avg_score": 80.0},
        {"source": "bad", "jobs": 25, "avg_score": 55.0},
    ]
    r = recommend({}, funnel={}, sources=sources, min_sample=20)
    assert any(rec["area"] == "sources" for rec in r["recommendations"])


# ---------------------------------------------------- response correlation

def test_correlation_rates():
    outreach = [{"status": "sent"}, {"status": "drafted"}]
    reminders = [
        {"applied_at": "2026-09-01T00:00:00+00:00",
         "response_received_at": "2026-09-04T00:00:00+00:00"},
        {},
    ]
    corr = response_correlation(reminders, outreach)
    assert corr["outreach_sent"] == 2
    assert corr["responses_received"] == 1
    assert corr["response_rate"] == 0.5
    assert corr["median_days_to_response"] == 3.0


def test_correlation_empty_safe():
    corr = response_correlation([], [])
    assert corr["response_rate"] is None
    assert corr["median_days_to_response"] is None
