from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Unified config spine (ARCHITECTURE_DECISION D24).

    Precedence: environment variables (JOBAGENT_*) > .env file > defaults.
    YAML country configs (config/countries/) and DB-backed settings layer on top
    for domain config; env vars always win for secrets/runtime overrides.
    """

    # --- AI providers (OpenRouter is Basil's default; DeepSeek for paid volume) ---
    openrouter_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    deepseek_api_key: str = ""
    usajobs_api_key: str = ""
    adzuna_api_key: str = ""
    adzuna_app_id: str = ""

    # --- Data paths ---
    db_path: str = "data/jobagent.db"
    resume_path: str = "data/resume.txt"
    profile_dir: str = "data/profile"          # M2: candidate evidence YAML
    countries_dir: str = "config/countries"    # M3: country strategy YAML

    # --- Scheduling ---
    scrape_interval_hours: int = 6

    # --- Salary filters (fallback; country YAML overrides per-country) ---
    min_salary: int = 150000
    min_hourly_rate: int = 95

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8085

    # --- Feature flags (D22: US-specific features disabled, not deleted) ---
    enable_salary_tools: bool = False      # salary calculator, offer comparison, tax estimation
    enable_career_advisor: bool = False    # career trajectory intelligence
    enable_success_predictor: bool = False # application success prediction
    enable_extension_autofill: bool = True # Chrome autofill/overlay integration
    enable_linkedin_guest: bool = False    # LinkedIn guest-API source (off by default, ToS discipline)

    # --- Gmail (M9; draft-only by default, sending is a deliberate act) ---
    allow_send: bool = False               # MUST be explicitly true + per-draft approval to ever send

    model_config = {
        "env_prefix": "JOBAGENT_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
