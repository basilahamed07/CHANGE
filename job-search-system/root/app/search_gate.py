"""No-resume gate for search + discovery.

A run must be driven by the candidate's OWN resume-derived keywords. Before
this gate a brand-new user could press "Scrape now" with no resume and the
scrapers silently fell back to hardcoded defaults ("AI Engineer",
"Machine Learning Engineer") — i.e. the search was not based on them at all.

The gate only applies to an authenticated request that has a per-user
workspace. The legacy / unauthenticated / testing path (no workspace bound)
keeps its previous behaviour, so existing tests are unaffected.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

NO_RESUME_MESSAGE = (
    "Upload a resume first — jobagent needs it to know which roles to search for."
)


async def require_resume_for_search(request: Request) -> None:
    """Raise 428 (Precondition Required) when the user has no usable resume.

    Returns ``True`` when a workspace user passed the gate, ``False`` when there
    is no workspace (gate intentionally not applied) so callers can tell the
    difference if they need to.
    """
    ws = getattr(request.state, "workspace", None)
    if ws is None:
        return
    if not await ws.db.has_usable_resume():
        raise HTTPException(status_code=428, detail=NO_RESUME_MESSAGE)
