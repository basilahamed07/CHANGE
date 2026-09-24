"""Regression tests for profile-table saves (found by the user-journey E2E).

The journey harness posted a body with a mistyped field name to
`/api/custom-qa`, `/api/work-history` and `/api/certifications` and got an
unhandled **500** — the DB layer's column guard raises ValueError and nothing
caught it. A bad field name is a CLIENT error: it must be a 400, never a crash.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import Database


@pytest.fixture
async def client(tmp_path):
    from app.main import create_app

    application = create_app(db_path=str(tmp_path / "profile.db"), testing=True)
    db = Database(str(tmp_path / "profile.db"))
    await db.init()
    application.state.db = db
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, db
    await db.close()


UNKNOWN_FIELD_BODIES = [
    ("/api/custom-qa", {"question": "Do you need sponsorship?", "answer": "Yes"}),
    ("/api/work-history", {"company": "Acme", "title": "Engineer",
                           "start_date": "2024-05", "current": True}),
    ("/api/certifications", {"name": "Azure AI Engineer", "issuer": "Microsoft"}),
    ("/api/skills", {"name": "Python", "level": "expert"}),
    ("/api/education", {"school": "Somewhere", "degree": "BSc", "year": 2023}),
    ("/api/languages", {"language": "English", "fluency": "native"}),
    ("/api/references", {"name": "Ref", "relation": "Manager"}),
]


@pytest.mark.parametrize("path,body", UNKNOWN_FIELD_BODIES)
async def test_unknown_field_is_a_400_not_a_500(client, path, body):
    ac, _db = client
    r = await ac.post(path, json=body)
    assert r.status_code == 400, f"{path} returned {r.status_code}: {r.text[:200]}"
    assert "invalid field" in r.text.lower()


VALID_SAVES = [
    ("/api/custom-qa", {"question_pattern": "Sponsorship?", "category": "visa",
                        "answer": "Yes"}),
    ("/api/work-history", {"company": "Changepond", "job_title": "AI Developer",
                           "start_month": 5, "start_year": 2024,
                           "is_current": 1, "description": "RAG systems."}),
    ("/api/certifications", {"name": "Azure AI Engineer",
                             "issuing_org": "Microsoft",
                             "date_obtained": "2025-01-01"}),
    ("/api/skills", {"name": "LangGraph", "proficiency": "advanced"}),
    ("/api/education", {"school": "E.G.S. Pillay", "degree_type": "bachelors",
                        "field_of_study": "CS", "grad_year": 2023}),
    ("/api/languages", {"language": "English", "proficiency": "fluent"}),
    ("/api/references", {"name": "Ref One", "relationship": "Manager",
                         "email": "ref@example.com"}),
]


@pytest.mark.parametrize("path,body", VALID_SAVES)
async def test_valid_fields_save_and_return_an_id(client, path, body):
    ac, _db = client
    r = await ac.post(path, json=body)
    assert r.status_code == 200, f"{path} returned {r.status_code}: {r.text[:200]}"
    assert r.json().get("ok") is True
    assert isinstance(r.json().get("id"), int)


async def test_non_object_body_is_rejected(client):
    ac, _db = client
    r = await ac.post("/api/custom-qa", json=["not", "an", "object"])
    assert r.status_code == 400
    r = await ac.post("/api/custom-qa", json={})
    assert r.status_code == 400
