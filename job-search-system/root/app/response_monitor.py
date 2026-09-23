"""M12 — Response monitor + feedback loop.

Deterministic-first email classification (Golden Rule 3): keyword/rule
scoring classifies recruiter replies into 8 classes; anything below the
confidence floor routes to REVIEW — never a silent high-impact change.

Classes (Phase 23 taxonomy):
    interview_invite | rejection | availability_request | more_info_request
    offer | auto_ack | out_of_office | unrelated

Feedback loop: aggregate stats produce HUMAN-READABLE recommendations only.
No auto weight-rewrites on small samples (Rule: evidence > hallucination).
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

CONFIDENCE_FLOOR = 0.70

# Ordered rule sets — first match wins; score = sum of matched rule weights.
RULES: list[tuple[str, float, re.Pattern]] = [
    # interview invites are high-signal
    ("interview_invite", 0.90, re.compile(
        r"\b(invit\w+|schedule|schedul\w+|calendar|calendly|next steps?|"
        r"interview (?:on|at|slot)|call (?:on|at)|zoom|google meet|teams link)\b", re.I)),
    ("offer", 0.95, re.compile(
        r"\b(offer letter|compensation package|we(?:'| a)?re (?:pleased|excited) to offer|"
        r"official offer|verbal offer)\b", re.I)),
    ("rejection", 0.85, re.compile(
        r"\b(unfortunately|regret to inform|not moving forward|won'?t be (?:moving|progressing)|"
        r"decided (?:not to|to move with other)|position has been filled|other candidates)\b", re.I)),
    ("availability_request", 0.75, re.compile(
        r"\b(what time works|your availability|available (?:on|this week|next week)|"
        r"good time (?:for|to) (?:a )?(?:call|chat|talk))\b", re.I)),
    ("more_info_request", 0.70, re.compile(
        r"\b(could you (?:share|send|provide)|please (?:share|send|provide)|"
        r"portfolio|references?|work samples?|notice period|salary expectations)\b", re.I)),
    ("out_of_office", 0.90, re.compile(
        r"\b(out of (?:the )?office|ooo|on (?:annual )?leave|away until|vacation reply|"
        r"limited (?:email )?access until)\b", re.I)),
    ("auto_ack", 0.70, re.compile(
        r"\b(thank you for (?:your )?(?:application|applying)|we have received|"
        r"application (?:has been )?received|no longer than \d+ (?:days|weeks)|"
        r"this is an automatic)\b", re.I)),
]

# Patterns that lower confidence: long personalized bodies look human-written,
# generic single-line acks look automatic.
PERSONAL_SIGNALS = re.compile(
    r"\b(I (?:read|reviewed|looked) (?:through|at|over) your|your experience (?:with|in)|"
    r"impressed by|standout|great fit for our team)\b", re.I)


@dataclass
class Classification:
    label: str          # 8 classes + "review" + "unrelated"
    confidence: float
    review: bool
    matched_rules: list[str]
    reason: str


def classify_email(subject: str = "", body: str = "",
                   sender: str = "") -> Classification:
    """Deterministic classifier. Pure function — no DB, no AI, no state."""
    text = f"{subject}\n{body}"
    low = text.lower()

    # Recruiter domains boost nothing by themselves, but no-reply senders
    # strongly signal auto-ack.
    if sender and re.match(r"no[-_.]?reply|donotreply|noreply@", sender.lower()):
        if not any(w in low for w in ("interview", "offer")):
            return Classification("auto_ack", 0.95, False,
                                  ["no_reply_sender"],
                                  "no-reply sender with non-engaging body")

    best_label, best_score, matched = "unrelated", 0.0, []
    for label, weight, pattern in RULES:
        m = pattern.search(text)
        if m:
            matched.append(label)
            # Strong direct hit beats accumulated weak signals
            if weight > best_score:
                best_label, best_score = label, weight

    # Personal signals raise a borderline hit into confidence
    if PERSONAL_SIGNALS.search(text):
        best_score = min(1.0, best_score + 0.10)

    if best_score == 0.0:
        return Classification("review", 0.0, True, [],
                              "no rule matched — human review")

    confidence = min(1.0, best_score)
    review = confidence < CONFIDENCE_FLOOR
    label = best_label if not review else "review"
    return Classification(label, round(confidence, 2), review, matched,
                          f"matched: {', '.join(matched) or 'none'}")


# ------------------------------------------------------- feedback loop

def recommend(weights: dict[str, float], funnel: dict[str, int],
              sources: list[dict], min_sample: int = 20) -> dict:
    """Aggregate stats → recommendations for HUMAN review.

    Never rewrites weights automatically; only proposes, and only when the
    sample size is large enough to be meaningful.
    """
    recs: list[dict] = []
    applied = funnel.get("applied", 0)
    interviewing = funnel.get("interviewing", 0)
    offered = funnel.get("offered", 0)
    rejected = funnel.get("rejected", 0)

    total_outcomes = interviewing + offered + rejected
    if total_outcomes >= min_sample:
        if interviewing + offered == 0 and rejected / max(total_outcomes, 1) > 0.8:
            recs.append({
                "area": "targeting",
                "suggestion": "Rejection rate above 80% with no interviews — "
                              "review search terms and minimum score cutoff",
                "sample": total_outcomes,
            })
        elif offered > 0 and rejected / max(total_outcomes, 1) < 0.3:
            recs.append({
                "area": "targeting",
                "suggestion": "Strong conversion — consider raising daily target",
                "sample": total_outcomes,
            })

    best = [s for s in sources if s.get("avg_score") and s["jobs"] >= min_sample]
    if len(best) >= 2:
        top, bottom = best[0], best[-1]
        if top["avg_score"] - bottom["avg_score"] >= 10:
            recs.append({
                "area": "sources",
                "suggestion": f"Source '{top['source']}' averages {top['avg_score']} "
                              f"vs '{bottom['source']}' at {bottom['avg_score']} — "
                              f"consider deprioritizing '{bottom['source']}'",
                "sample": top["jobs"] + bottom["jobs"],
            })

    if applied < min_sample:
        recs.append({
            "area": "sample_size",
            "suggestion": f"Only {applied} applications so far — keep applying; "
                          f"recommendations need ~{min_sample} for signal",
            "sample": applied,
        })

    return {"recommendations": recs, "review_required": True,
            "auto_rewrite_performed": False,
            "generated_at": datetime.now(timezone.utc).isoformat()}


def response_correlation(reminders: list[dict], outreach: list[dict],
                         now: datetime | None = None) -> dict:
    """Outreach ↔ response correlation + time-to-first-response inputs."""
    now = now or datetime.now(timezone.utc)
    sent = [o for o in outreach if o.get("status") in ("sent", "drafted")]
    with_response = [r for r in reminders if r.get("response_received_at")]
    ttfr: list[float] = []
    for r in with_response:
        base = r.get("applied_at") or r.get("outreach_sent_at")
        if base:
            try:
                dt = (datetime.fromisoformat(r["response_received_at"])
                      - datetime.fromisoformat(base)).total_seconds() / 86400
                if dt >= 0:
                    ttfr.append(round(dt, 1))
            except (ValueError, TypeError):
                continue
    return {
        "outreach_sent": len(sent),
        "responses_received": len(with_response),
        "response_rate": round(len(with_response) / len(sent), 3) if sent else None,
        "median_days_to_response": sorted(ttfr)[len(ttfr) // 2] if ttfr else None,
    }


def followup_due_date(status: str, from_date: datetime | None = None) -> datetime:
    """When the next follow-up on this status becomes due (cadence config)."""
    from_date = from_date or datetime.now(timezone.utc)
    days = {"prepared": 3, "applied": 7, "interviewing": 5}.get(status, 7)
    return from_date + timedelta(days=days)
