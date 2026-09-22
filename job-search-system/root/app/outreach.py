"""M9: Outreach engine — audience-specific variants + Gmail DRAFTS (never send).

Golden Rules enforced here:
- Rule 6 (DEFAULT = CREATE DRAFT, never send): the ONLY output of this module is
  drafts. Sending requires (a) JOBAGENT_ALLOW_SEND=true AND (b) per-message
  approval. There is no code path in M9 that sends a message.
- Rule 4 (deterministic): variant selection, limits, dedup and rendering are
  pure Python. AI wording may layer onto templates later — not required.
- Critical Test #4: creating outreach twice MUST NOT create a second draft.
  Enforced at the service layer (unique (job_id, audience) constraint + check)
  AND at the provider layer (thread-level draft dedup).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

AUDIENCES = ("recruiter", "hiring_manager", "referral", "followup")
DEFAULT_SEQUENCES = "config/outreach_sequences.yaml"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# --------------------------------------------------------------------------
# Sequences config


@dataclass
class Sequence:
    audience: str
    channel: str
    subject: str
    body: str


@dataclass
class OutreachLimits:
    max_outreach_per_day: int = 12
    per_company_daily_cap: int = 2
    followup_wait_days: int = 6


@dataclass
class OutreachIdentity:
    sender_name: str = "Basil Ahamed H"
    sender_email: str = "basilahamed46@gmail.com"


def load_sequences(path: str = DEFAULT_SEQUENCES) -> tuple[dict[str, Sequence], OutreachLimits, OutreachIdentity]:
    """Load sequences/limits/identity from YAML. Raises on missing file (fail-loud config)."""
    p = Path(path)
    if not p.exists():
        # Fall back to the packaged default location relative to app root
        alt = Path(__file__).resolve().parents[1] / "config" / "outreach_sequences.yaml"
        p = alt if alt.exists() else p
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    identity = OutreachIdentity(
        sender_name=(data.get("identity") or {}).get("sender_name", "Basil Ahamed H"),
        sender_email=(data.get("identity") or {}).get("sender_email", ""),
    )
    lim = data.get("limits") or {}
    limits = OutreachLimits(
        max_outreach_per_day=int(lim.get("max_outreach_per_day", 12)),
        per_company_daily_cap=int(lim.get("per_company_daily_cap", 2)),
        followup_wait_days=int(lim.get("followup_wait_days", 6)),
    )
    seqs: dict[str, Sequence] = {}
    for audience, raw in (data.get("sequences") or {}).items():
        if audience not in AUDIENCES:
            continue
        seqs[audience] = Sequence(
            audience=audience,
            channel=(raw.get("channel") or "email"),
            subject=raw.get("subject", ""),
            body=raw.get("body", ""),
        )
    for required in ("recruiter", "hiring_manager"):
        if required not in seqs:
            raise ValueError(f"outreach_sequences.yaml missing required sequence: {required}")
    return seqs, limits, identity


# --------------------------------------------------------------------------
# Deterministic rendering


def render_message(sequence: Sequence, contact_name: str, job_title: str,
                   company: str, identity: OutreachIdentity) -> dict:
    """Fill placeholders deterministically. No AI, no surprise content."""
    name = (contact_name or "").strip() or "there"
    subs = {
        "contact_name": name,
        "job_title": job_title or "the role",
        "company": company or "your company",
        "sender_name": identity.sender_name,
        "sender_email": identity.sender_email,
    }

    def _sub(text: str) -> str:
        out = re.sub(r"\{(\w+)\}", lambda m: subs.get(m.group(1), m.group(0)), text or "")
        return re.sub(r"\n{3,}", "\n\n", out).strip()

    return {
        "subject": _sub(sequence.subject),
        "body": _sub(sequence.body),
    }


# --------------------------------------------------------------------------
# Gmail provider — DRAFT-ONLY (interface ready for M10+ approval flow)


class GmailProvider:
    """Gmail REST draft provider. NO send capability exists here, period.

    - Credentials: access token from settings (OAuth flow handled outside M9;
      Basil pastes a token or the UI runs the installed-app flow later).
    - Thread-level dedup: before creating a draft, search the thread; if a draft
      already exists for this (job, audience), return it unchanged.
    - Fallback: when no token is configured, drafts are stored locally
      (outreach_messages table) and marked provider='local' — the pipeline
      completes without Gmail, and sync can happen later.
    """

    name = "gmail"
    DRAFTS_URL = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
    THREADS_URL = "https://gmail.googleapis.com/gmail/v1/users/me/threads"

    def __init__(self, token: str = ""):
        self.token = token or os.getenv("JOBAGENT_GMAIL_TOKEN", "")
        self.available = bool(self.token)

    async def create_draft(self, to: str, subject: str, body: str,
                           thread_hint: str = "") -> dict:
        """Create a Gmail draft. Returns {id, provider:'gmail', threadId?}.
        Raises on HTTP failure — the SERVICE handles fallback."""
        import base64

        import httpx
        message = {
            "message": {
                "to": [{"email": to}],
                "subject": subject,
                "text": body,
            }
        }
        # gmailformat: proper RFC2822 raw message
        raw_msg = (
            f"To: {to}\r\nSubject: {subject}\r\nContent-Type: text/plain; charset=\"UTF-8\"\r\n\r\n{body}"
        )
        raw_b64 = base64.urlsafe_b64encode(raw_msg.encode("utf-8")).decode("ascii")
        payload = {"message": {"raw": raw_b64}}
        if thread_hint:
            payload["message"]["threadId"] = thread_hint

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                self.DRAFTS_URL,
                headers={"Authorization": f"Bearer {self.token}",
                         "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        return {"id": data.get("id", ""), "provider": "gmail",
                "thread_id": (data.get("message") or {}).get("threadId", "")}

    async def find_existing_draft(self, subject: str) -> dict | None:
        """Thread-level dedup: look for an existing draft with this subject."""
        import httpx
        if not self.available:
            return None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self.DRAFTS_URL,
                    params={"q": f"subject:{subject}"},
                    headers={"Authorization": f"Bearer {self.token}"})
                resp.raise_for_status()
                drafts = resp.json().get("drafts", []) or []
            return drafts[0] if drafts else None
        except Exception as e:
            logger.warning("Gmail draft lookup failed (dedup degrades to DB): %s", e)
            return None


# --------------------------------------------------------------------------
# OutreachService — the only entry point routers should call


class OutreachService:
    def __init__(self, db, sequences: dict[str, Sequence], limits: OutreachLimits,
                 identity: OutreachIdentity, gmail: GmailProvider | None = None):
        self.db = db
        self.sequences = sequences
        self.limits = limits
        self.identity = identity
        self.gmail = gmail or GmailProvider()

    # ------------------------------------------------------------- helpers

    async def _daily_count(self) -> int:
        return await self.db.count_outreach_since(
            _iso(_now_utc() - timedelta(days=1)))

    async def _company_count_today(self, company: str) -> int:
        return await self.db.count_outreach_since(
            _iso(_now_utc() - timedelta(days=1)), company=company)

    @staticmethod
    def _pick_audience(job: dict, requested: str | None) -> str:
        if requested:
            if requested not in AUDIENCES:
                raise ValueError(f"unknown audience: {requested}")
            return requested
        # Deterministic default: contact on file decides the audience
        email = (job.get("hiring_manager_email") or "").strip()
        title = (job.get("hiring_manager_title") or "").strip()
        if not email:
            return "recruiter"  # no contact -> generic recruiter sequence
        from app.contact_providers import classify_role
        role = classify_role(title or email)
        if role == "recruiter":
            return "recruiter"
        if role == "hiring_manager":
            return "hiring_manager"
        return "recruiter"

    # -------------------------------------------------------------- main API

    async def create_outreach(self, job_id: int, audience: str | None = None,
                              contact_email: str = "", contact_name: str = "",
                              force_audience: bool = True) -> dict:
        """Create outreach for a job. IDEMPOTENT per (job, audience).

        Critical Test #4 lives here: a second call with the same arguments
        returns the EXISTING message (status 'already_exists'), and no second
        draft is created at Gmail or in the DB.
        """
        job = await self.db.get_job(job_id)
        if not job:
            raise ValueError(f"job {job_id} not found")

        audience = self._pick_audience(job, audience if force_audience else None)

        # --- Critical Test #4: dedup first, always -------------------------
        existing = await self.db.get_outreach(job_id, audience)
        if existing:
            return {"status": "already_exists", "message": existing,
                    "reason": "one outreach per (job, audience) — Critical Test #4"}

        # --- Anti-spam caps -------------------------------------------------
        daily = await self._daily_count()
        if daily >= self.limits.max_outreach_per_day:
            return {"status": "capped", "reason":
                    f"daily cap reached ({daily}/{self.limits.max_outreach_per_day})"}
        company_today = await self._company_count_today(job.get("company", ""))
        if company_today >= self.limits.per_company_daily_cap:
            return {"status": "capped", "reason":
                    f"company cap reached ({company_today}/{self.limits.per_company_daily_cap} today for {job.get('company')})"}

        seq = self.sequences.get(audience)
        if seq is None:
            raise ValueError(f"no sequence configured for audience: {audience}")

        to_email = (contact_email or job.get("hiring_manager_email") or "").strip()
        rendered = render_message(seq, contact_name or job.get("hiring_manager_name", ""),
                                  job.get("title", ""), job.get("company", ""),
                                  self.identity)

        # --- Provider: Gmail draft (dedup there too) or local fallback -----
        draft_id, provider, thread_id = "", "local", ""
        if to_email:
            existing_gmail = await self.gmail.find_existing_draft(rendered["subject"])
            if existing_gmail:
                draft_id = existing_gmail.get("id", "")
                provider = "gmail"
                thread_id = ""
            elif self.gmail.available:
                try:
                    draft = await self.gmail.create_draft(
                        to=to_email, subject=rendered["subject"], body=rendered["body"])
                    draft_id, provider = draft["id"], "gmail"
                    thread_id = draft.get("thread_id", "")
                except Exception as e:
                    logger.warning("Gmail draft creation failed -> local fallback: %s", e)
        msg_id = await self.db.insert_outreach(
            job_id=job_id, audience=audience, channel=seq.channel,
            to_email=to_email, subject=rendered["subject"], body=rendered["body"],
            provider=provider, draft_id=draft_id, thread_id=thread_id,
            status="drafted")
        message = await self.db.get_outreach_by_id(msg_id)
        return {"status": "created", "message": message}

    async def create_followup(self, job_id: int) -> dict:
        """Follow-up variant — only after followup_wait_days since the first outreach."""
        first = await self.db.get_outreach(job_id, "recruiter") or \
            await self.db.get_outreach(job_id, "hiring_manager")
        if not first:
            raise ValueError("no initial outreach to follow up on")
        created_at = datetime.fromisoformat(str(first["created_at"]).replace("Z", "+00:00"))
        wait = timedelta(days=self.limits.followup_wait_days)
        if _now_utc() - created_at < wait:
            return {"status": "too_soon",
                    "reason": f"follow-up allowed after {self.limits.followup_wait_days} days "
                              f"({(wait - (_now_utc() - created_at)).days}d left)"}
        return await self.create_outreach(job_id, audience="followup")

    async def list_messages(self, limit: int = 100) -> list[dict]:
        return await self.db.list_outreach(limit)
