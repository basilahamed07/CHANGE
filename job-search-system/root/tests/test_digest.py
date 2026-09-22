import pytest
from app.database import Database
from app.digest import generate_digest


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_generate_digest(db):
    job_id = await db.insert_job("Senior Dev", "Acme Corp", "Remote", 150000, 200000,
                                  "Build things", "http://acme.com/job/1", None, "url", None)
    await db.insert_score(job_id, 85, ["good fit"], ["none"], ["python"])

    result = await generate_digest(db, min_score=60, hours=24)
    assert result["job_count"] == 1
    assert "Senior Dev" in result["body"]
    assert "Acme Corp" in result["body"]
    assert result["jobs"][0]["match_score"] == 85


@pytest.mark.asyncio
async def test_generate_digest_empty(db):
    result = await generate_digest(db, min_score=60, hours=24)
    assert result["job_count"] == 0
    assert result["jobs"] == []


@pytest.mark.asyncio
async def test_generate_digest_score_filter(db):
    job_id = await db.insert_job("Dev", "Co", "NYC", None, None,
                                  "desc", "http://x", None, "url", None)
    await db.insert_score(job_id, 40, ["ok"], [], [])

    result = await generate_digest(db, min_score=60, hours=24)
    assert result["job_count"] == 0  # score too low
