"""M3: Country strategy registry (Golden Rule 8 — country is a first-class entity).

Loads config/countries/*.yaml. Adding a country = dropping a YAML file in that
directory. ZERO core-code changes. Schema is validated on load (fail-loud on
bad schema so strategy never silently runs on broken config).

The registry is STRATEGY only: what countries we target, what work types are
allowed, visa/sponsorship keywords, salary floors. Location *classification*
(location string -> region) stays in location_classifier.py; the registry
feeds it alias/city data via classification_terms().
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_REQUIRED_FIELDS = ("code", "name", "enabled")
_KNOWN_FIELDS = {
    "code", "name", "region", "enabled", "aliases", "cities", "work_types",
    "visa", "salary", "search",
}
_VISA_FIELDS = {"requires_sponsorship", "sponsorship_keywords"}


class CountryConfigError(Exception):
    """Raised when a country YAML violates the schema (fail-loud)."""


class Country:
    """One country strategy, loaded and validated from YAML."""

    def __init__(self, data: dict, source: Path):
        unknown = set(data) - _KNOWN_FIELDS
        if unknown:
            raise CountryConfigError(
                f"{source.name}: unknown field(s) {sorted(unknown)}")
        for field in _REQUIRED_FIELDS:
            if field not in data:
                raise CountryConfigError(f"{source.name}: missing required field '{field}'")
        self.code: str = str(data["code"]).upper()
        self.name: str = str(data["name"])
        self.enabled: bool = bool(data["enabled"])
        self.source: Path = source
        # 'region' is the canonical string the location classifier emits and the
        # value stored in jobs.location_region (e.g. UK, UAE). Defaults to name
        # for countries where display name == region string.
        self.region_str: str = str(data.get("region") or self.name)

        # 'uk' alias would collide with word-boundary matches elsewhere; keep codes sane.
        if len(self.code) != 2 or not self.code.isalpha():
            raise CountryConfigError(f"{source.name}: 'code' must be a 2-letter country code")

        self.aliases: list[str] = [str(a).lower() for a in (data.get("aliases") or [])]
        self.cities: list[str] = [str(c).lower() for c in (data.get("cities") or [])]

        wt = data.get("work_types") or {}
        self.work_types: dict[str, bool] = {
            "remote": bool(wt.get("remote", True)),
            "hybrid": bool(wt.get("hybrid", True)),
            "onsite": bool(wt.get("onsite", True)),
        }

        visa = data.get("visa") or {}
        missing_visa = _VISA_FIELDS - set(visa)
        if missing_visa:
            raise CountryConfigError(
                f"{source.name}: visa section missing {sorted(missing_visa)}")
        self.requires_sponsorship: bool = bool(visa["requires_sponsorship"])
        self.sponsorship_keywords: list[str] = [
            str(k).lower() for k in (visa["sponsorship_keywords"] or [])
        ]

        salary = data.get("salary") or {}
        self.salary_currency: str = str(salary.get("currency", ""))
        self.salary_min: int | None = (
            int(salary["min"]) if salary.get("min") is not None else None
        )

        self.extra_search_terms: list[str] = [
            str(t) for t in ((data.get("search") or {}).get("extra_terms") or [])
        ]

    @property
    def region(self) -> str:
        """The region string the location classifier emits for this country."""
        return self.region_str

    def allows_work_type(self, work_type: str | None) -> bool:
        if not work_type:
            return True
        return self.work_types.get(str(work_type).lower(), True)

    def to_dict(self) -> dict:
        return {
            "code": self.code, "name": self.name, "region": self.region_str,
            "enabled": self.enabled,
            "aliases": self.aliases, "cities": self.cities,
            "work_types": self.work_types,
            "visa": {
                "requires_sponsorship": self.requires_sponsorship,
                "sponsorship_keywords": self.sponsorship_keywords,
            },
            "salary": {"currency": self.salary_currency, "min": self.salary_min},
            "search": {"extra_terms": self.extra_search_terms},
            "source": self.source.name,
        }


class CountryRegistry:
    """Loads every countries_dir/*.yaml. Zero-code country addition."""

    def __init__(self, countries_dir: str | Path):
        self.countries_dir = Path(countries_dir)
        self.countries: dict[str, Country] = {}  # keyed by region name (classifier string)

    def load(self) -> "CountryRegistry":
        self.countries = {}
        if not self.countries_dir.exists():
            logger.warning("Countries dir missing: %s (no country strategy active)",
                           self.countries_dir)
            return self
        files = sorted(self.countries_dir.glob("*.yaml"))
        for path in files:
            try:
                data = yaml.safe_load(path.read_text()) or {}
                country = Country(data, path)
                if country.region in self.countries:
                    raise CountryConfigError(
                        f"{path.name}: duplicate region '{country.region}' "
                        f"(already loaded from {self.countries[country.region].source.name})")
                self.countries[country.region] = country
            except CountryConfigError:
                raise  # schema errors must fail loud
            except Exception as e:
                raise CountryConfigError(f"{path.name}: unreadable ({e})") from e
        logger.info("Country registry: %d countries loaded (%s)",
                    len(self.countries),
                    ", ".join(c.code for c in self.countries.values()))
        return self

    # --- lookups ---------------------------------------------------------

    def get(self, region: str) -> Country | None:
        return self.countries.get(region)

    def enabled_countries(self) -> list[Country]:
        return [c for c in self.countries.values() if c.enabled]

    def region_names(self) -> list[str]:
        """Region strings for ALL loaded countries (enabled or not)."""
        return list(self.countries.keys())

    def enabled_region_names(self) -> list[str]:
        return [c.region for c in self.enabled_countries()]

    def classification_terms(self) -> dict[str, str]:
        """alias/city -> region name, for the location classifier (rule-based pass).

        Terms are word-boundary matched, longest first, so 'united arab emirates'
        wins before 'uae'.
        """
        terms: dict[str, str] = {}
        for region, c in self.countries.items():
            for t in [*c.aliases, *c.cities]:
                terms[t] = region
        return terms

    def summary(self) -> dict:
        return {
            "countries_dir": str(self.countries_dir),
            "count": len(self.countries),
            "enabled": [c.code for c in self.enabled_countries()],
            "countries": [c.to_dict() for c in self.countries.values()],
        }
