"""Deterministic ATS lint tests — no LLM, no network, no app instance.

The lint is a GATE on shipped resumes, so it must be boringly predictable:
same text in, same report out.
"""

from __future__ import annotations

from app.ats import ATS_PASS_THRESHOLD, ats_lint, ats_pass, jd_keywords

GOOD_RESUME = """Jordan Candidate
jordan@example.com | +49 30 1234567 | linkedin.com/in/jordancand

SUMMARY
Senior AI engineer with eight years building production RAG and agent systems.

EXPERIENCE
Acme Corp — Senior AI Engineer (2021-2026)
- Built a retrieval augmented generation pipeline serving 40 requests per second
- Led migration of the ranking service from monolith to FastAPI microservices
- Designed an evaluation harness for LLM output quality

EDUCATION
MSc Computer Science, Technical University

SKILLS
Python, FastAPI, LangChain, vector databases, RAG, Docker, Kubernetes, SQL
"""

GOOD_JD = """We are hiring a Senior AI Engineer to build retrieval augmented
generation systems. You will work with Python, FastAPI, LangChain and vector
databases, deploy on Kubernetes in Docker, and own evaluation of LLM output
quality. Experience with RAG pipelines and ranking services is essential.
"""


def test_good_resume_passes():
    report = ats_lint(GOOD_RESUME, GOOD_JD)
    assert report.ok, report.failures
    assert report.score >= ATS_PASS_THRESHOLD
    assert ats_pass(report)
    assert set(report.sections_found) >= {"summary", "experience", "education", "skills"}
    assert report.keyword_coverage > 0.7


def test_missing_contact_fails():
    report = ats_lint(GOOD_RESUME.replace("jordan@example.com", "")
                                .replace("+49 30 1234567", ""), GOOD_JD)
    assert not report.ok
    assert any(i.code == "missing_contact" for i in report.issues)


def test_missing_sections_fails():
    body = "\n".join(
        ln for ln in GOOD_RESUME.splitlines()
        if ln.strip() not in {"SUMMARY", "EXPERIENCE", "EDUCATION", "SKILLS"})
    report = ats_lint(body, GOOD_JD)
    assert any(i.code == "missing_standard_sections" for i in report.issues)
    assert not report.ok


def test_column_layout_is_a_hard_hazard():
    tabbed = GOOD_RESUME.replace(
        "Acme Corp — Senior AI Engineer (2021-2026)",
        "Acme Corp\tSenior AI Engineer\t2021-2026")
    report = ats_lint(tabbed, GOOD_JD)
    assert any(i.code == "layout_hazard" and i.severity == "fail"
               for i in report.issues)


def test_low_keyword_coverage_fails_and_reports_missing():
    jd = GOOD_JD + (" Terraform, Kafka, Spark, Airflow, Snowflake, dbt, Scala, "
                    "Rust, Go, Kafka Streams, Flink, Beam, Presto, Trino.")
    report = ats_lint(GOOD_RESUME, jd)
    assert any(i.code == "low_keyword_coverage" for i in report.issues)
    assert report.missing_keywords
    assert not ats_pass(report)


def test_missing_keywords_are_the_jd_terms_absent_from_resume():
    jd = "We need Kubernetes and Terraform and Nomad experience."
    missing = ats_lint(GOOD_RESUME, jd).missing_keywords
    assert "terraform" in missing
    assert "nomad" in missing
    assert "kubernetes" not in missing     # Kubernetes is in SKILLS


def test_inconsistent_bullets_warn_only():
    mixed = GOOD_RESUME.replace("- Built a retrieval", "* Built a retrieval")
    report = ats_lint(mixed, GOOD_JD)
    assert any(i.code == "inconsistent_bullets" for i in report.issues)
    # A warning never blocks a package on its own.
    assert not any(i.code == "inconsistent_bullets" and i.severity == "fail"
                   for i in report.issues)


def test_empty_resume_fails_hard():
    report = ats_lint("", GOOD_JD)
    assert not report.ok
    assert report.score < ATS_PASS_THRESHOLD
    assert report.word_count == 0


def test_no_job_description_skips_keyword_gate():
    report = ats_lint(GOOD_RESUME, "")
    assert report.keyword_coverage == 1.0
    assert not any("keyword" in i.code for i in report.issues)
    assert ats_pass(report)


def test_report_is_deterministic():
    a = ats_lint(GOOD_RESUME, GOOD_JD).to_dict()
    b = ats_lint(GOOD_RESUME, GOOD_JD).to_dict()
    assert a == b


def test_jd_keywords_drop_stopwords_and_strip_punctuation():
    kws = jd_keywords("We are looking for a C++ engineer who knows CI/CD and Node.js.")
    assert "c++" in kws or "c" in kws       # punctuation kept inside the token
    assert "node.js" in kws
    assert "the" not in kws and "looking" not in kws and "for" not in kws


# --- regressions for the three bugs that kept this suite red (2026-10-03) -----

def test_contact_line_with_pipes_is_not_a_layout_hazard():
    """BUG A: `email | phone | linkedin` is a contact block, not a table.

    The pipe check used to fire on any line with 2+ pipes, which failed almost
    every real resume — the conventional single-line contact block included.
    """
    report = ats_lint(GOOD_RESUME, GOOD_JD)
    assert not any(i.code == "layout_hazard" for i in report.issues)


def test_real_pipe_table_still_fails_the_layout_hazard():
    """The other side of BUG A: a genuine pipe-separated table is still caught."""
    tabled = GOOD_RESUME.replace(
        "- Built a retrieval augmented generation pipeline serving 40 requests per second",
        "Title | Stack | Dates | Metric")
    report = ats_lint(tabled, GOOD_JD)
    assert any(i.code == "layout_hazard" and i.severity == "fail"
               for i in report.issues)


def test_year_range_and_date_are_not_phone_numbers():
    """BUG B: `2021-2026` / `2024-01-15` must not satisfy the contact check.

    The loose phone regex matched them, so a resume with NO phone and NO email
    still reported a contact block and never raised `missing_contact`.
    """
    body = GOOD_RESUME.replace("jordan@example.com", "").replace("+49 30 1234567", "")
    assert "2021-2026" in body
    report = ats_lint(body, GOOD_JD)
    assert any(i.code == "missing_contact" for i in report.issues)


def test_a_real_international_phone_still_counts_as_contact():
    """Regression guard for BUG B: >=10 digits must not be over-tightened."""
    body = GOOD_RESUME.replace("jordan@example.com", "")   # phone kept
    report = ats_lint(body, GOOD_JD)
    assert not any(i.code == "missing_contact" for i in report.issues)
    assert any(i.code == "missing_email" for i in report.issues)   # warn only


def test_keyword_floor_is_sixty_percent():
    """BUG C: coverage below 60% is a hard failure, not a warning."""
    from app.ats import KEYWORD_COVERAGE_FLOOR, KEYWORD_COVERAGE_THIN
    assert KEYWORD_COVERAGE_FLOOR == 0.6
    assert KEYWORD_COVERAGE_THIN > KEYWORD_COVERAGE_FLOOR
