"""Stage-5 HYBRID_SCORE — H2: score-all must not score against an empty profile.

`build_hybrid_matcher_async` reads **attributes** off the state it is handed:
`evidence_store`, `country_registry`, `embedding_client`. The router used to hand
it a stub carrying only `.matcher`, so the profile was built empty — no verified
skills, no corpus, no visa keywords — and every job scored a flat
`skills=50 / semantic=50`. The determinstic layer looked healthy while it was
actually measuring nothing.

These tests pin both halves of the fix: the assembled state carries the real
per-request dependencies, and the endpoints built from it report a populated
profile.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import yaml as _yaml
from httpx import ASGITransport, AsyncClient

from app.database import Database


async def _app(tmp_path, skill: str = "LangChain"):
    from app.main import create_app
    from app.evidence_store import EvidenceStore

    db_path = str(tmp_path / "hybrid.db")
    application = create_app(db_path=db_path, testing=True)
    db = Database(db_path)
    await db.init()
    application.state.db = db

    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    (profile_dir / "skills.yaml").write_text(_yaml.safe_dump(
        {"claims": [{"id": "s1", "value": skill, "status": "VERIFIED",
                     "source": "test"}]}))
    store = EvidenceStore(profile_dir=str(profile_dir))

    application.state.evidence_store = store
    application.state.country_registry = None
    application.state.embedding_client = None
    return application, db, store


class _FakeRequest:
    """Minimal stand-in: no workspace, so ai_state_for falls back to app state."""

    def __init__(self, app):
        self.app = app
        self.state = SimpleNamespace()


# ------------------------------------------------------- the assembled state


async def test_hybrid_state_carries_the_evidence_store(tmp_path):
    from app.routers.matching import _hybrid_state

    application, db, store = await _app(tmp_path)
    state = await _hybrid_state(_FakeRequest(application))

    assert state.evidence_store is store
    assert state.country_registry is None          # shared app-level dep present
    assert hasattr(state, "embedding_client")
    await db.close()


async def test_hybrid_state_profile_is_populated_not_empty(tmp_path):
    """THE H2 assertion: verified skills + corpus reach the profile builder."""
    from app.matching_service import build_hybrid_matcher_async
    from app.routers.matching import _hybrid_state

    application, db, store = await _app(tmp_path, skill="LangChain")
    state = await _hybrid_state(_FakeRequest(application))

    _, meta = await build_hybrid_matcher_async(state, db)

    assert meta["verified_skills"] >= 1, "profile was built empty (H2)"
    assert meta["corpus_lines"] >= 1
    assert meta["do_not_use_skills"] == 0
    await db.close()


async def test_an_empty_state_still_reports_zero_so_the_difference_is_visible(tmp_path):
    """Guard on the guard: without a store the profile really is empty."""
    from app.matching_service import build_hybrid_matcher_async

    application, db, _ = await _app(tmp_path)
    stub = SimpleNamespace()          # the old `.matcher`-only stub, no attrs
    _, meta = await build_hybrid_matcher_async(stub, db)
    assert meta["verified_skills"] == 0
    assert meta["corpus_lines"] == 0
    await db.close()


# ---------------------------------------------------------------- endpoints


async def test_matching_status_reports_the_real_profile(tmp_path):
    """GET /api/matching/status must not be the empty-profile path either."""
    application, db, _ = await _app(tmp_path)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get("/api/matching/status")
        assert r.status_code == 200
        body = r.json()
        assert body["engine"] == "hybrid-m6"
        assert body["verified_skills"] >= 1, "status endpoint still builds an empty profile"
        assert body["corpus_lines"] >= 1
    await db.close()


async def test_score_all_returns_a_machine_readable_run_summary(tmp_path):
    """The endpoint contract, independent of how many jobs happen to qualify."""
    application, db, _ = await _app(tmp_path)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/api/matching/score-all")
        assert r.status_code == 200
        body = r.json()
        assert body["engine"] == "hybrid-m6"
        assert set(body) >= {"scored", "total", "avg", "blockers", "engine"}
        # meta must be present when anything was scored — and must never be
        # the silently-empty profile the stub used to produce.
        if body["scored"]:
            assert body["meta"]["verified_skills"] >= 1
    await db.close()
