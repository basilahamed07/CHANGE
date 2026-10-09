from app.company_registry import board_tokens, companies_for, load_company_registry


def test_registry_has_initial_ats_boards():
    assert board_tokens("greenhouse") == ["cloudflare", "datadog", "gitlab", "vercel"]
    assert board_tokens("lever") == ["spotify", "palantir"]
    assert "linear" in board_tokens("ashby")


def test_registry_filters_country_without_hiding_unscoped_records(tmp_path):
    path = tmp_path / "registry.yaml"
    path.write_text(
        "companies:\n"
        "  - id: sg-only\n"
        "    countries: [SG]\n"
        "    ats: {type: greenhouse, board: sg}\n"
        "  - id: global\n"
        "    ats: {type: greenhouse, board: global}\n",
        encoding="utf-8",
    )
    assert [c["id"] for c in companies_for("greenhouse", "SG", path)] == [
        "sg-only", "global"
    ]
    assert [c["id"] for c in companies_for("greenhouse", "DE", path)] == ["global"]


def test_malformed_registry_is_safe(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("companies: [not-a-record]", encoding="utf-8")
    assert load_company_registry(path) == []
    assert board_tokens("greenhouse", path) == []
