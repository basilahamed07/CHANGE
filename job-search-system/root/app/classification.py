"""STAGE-2 CLASSIFY — structured location classification (2026-09-30).

Answers ONLY: where is this job, how confident are we, what work type?
It never decides eligibility (Stage 3 owns that).

PRIORITY CHAIN (strongest evidence first — task §3):
  1. STRUCTURED_COUNTRY   explicit country field / ISO code in metadata
  2. TEXT_LOCATION        explicit country name in the location text
                          (incl. aliases: UK/U.K./Great Britain → GB)
  3. CITY_MAP             city-only location ("Berlin" → DE)
  4. DESCRIPTION          deterministic description evidence
                          ("Location:", "Based in:", …)
  5. ATS_METADATA         JobPosting/ATS structured fields if present
  6. SOURCE_HINT          the country the source searched under — HINT ONLY,
                          recorded as LOW confidence, never treated as truth
  7. AI_FALLBACK          bounded LLM classification, validated
  8. UNKNOWN              honest unknown — never fabricate a country

Remote handling: "Remote - India" → IN (REMOTE, HIGH); "Remote - APAC" →
UNKNOWN + region APAC; "Remote Worldwide" → UNKNOWN + GLOBAL. Source country
is NEVER the answer by default (§10): a job found under the SG search that
says "Kuala Lumpur" is MY.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# --- Confidence + source vocabularies (task §4/§14) ------------------------
CONF_HIGH = "HIGH"
CONF_MEDIUM = "MEDIUM"
CONF_LOW = "LOW"
CONF_UNKNOWN = "UNKNOWN"

SRC_STRUCTURED_COUNTRY = "STRUCTURED_COUNTRY"
SRC_STRUCTURED_LOCATION = "STRUCTURED_LOCATION"
SRC_TEXT_LOCATION = "TEXT_LOCATION"
SRC_CITY_MAP = "CITY_MAP"
SRC_ATS_METADATA = "ATS_METADATA"
SRC_DESCRIPTION = "DESCRIPTION"
SRC_SOURCE_HINT = "SOURCE_HINT"
SRC_AI_FALLBACK = "AI_FALLBACK"
SRC_UNKNOWN = "UNKNOWN"

REMOTE = "REMOTE"
HYBRID = "HYBRID"
ONSITE = "ONSITE"
UNKNOWN_WORK_TYPE = ""

UNKNOWN = "UNKNOWN"
GLOBAL = "GLOBAL"

# --- Country normalization (task §5) — ONE canonical table -----------------
# code → (display name, [aliases incl. cities fed by registry too])
COUNTRY_ALIASES: dict[str, tuple[str, tuple[str, ...]]] = {
    "DE": ("Germany", ("germany", "deutschland", "de")),
    "NL": ("Netherlands", ("netherlands", "holland", "the netherlands", "nl")),
    "IE": ("Ireland", ("ireland", "republic of ireland", "eire", "ie")),
    "GB": ("United Kingdom", ("uk", "u.k.", "united kingdom", "great britain",
                              "britain", "gb", "england", "scotland", "wales")),
    "SG": ("Singapore", ("singapore", "sg")),
    "AE": ("United Arab Emirates", ("united arab emirates", "uae", "u.a.e.",
                                    "emirates", "ae")),
    "IN": ("India", ("india", "in")),
    "CA": ("Canada", ("canada", "ca")),
    "AU": ("Australia", ("australia", "au")),
    "PL": ("Poland", ("poland", "pl")),
}

# City → country code (task §6). Deterministic, centralized, tested.
# Extend via config/countries YAML cities (already loaded in the registry);
# this table covers the canonical examples + common variants.
CITY_TO_COUNTRY: dict[str, str] = {
    # DE
    "berlin": "DE", "munich": "DE", "münchen": "DE", "frankfurt": "DE",
    "hamburg": "DE", "cologne": "DE", "köln": "DE", "stuttgart": "DE",
    "dusseldorf": "DE", "düsseldorf": "DE", "leipzig": "DE", "munich/de": "DE",
    # NL
    "amsterdam": "NL", "rotterdam": "NL", "the hague": "NL", "den haag": "NL",
    "utrecht": "NL", "eindhoven": "NL", "groningen": "NL",
    # IE
    "dublin": "IE", "cork": "IE", "galway": "IE", "limerick": "IE",
    # GB
    "london": "GB", "manchester": "GB", "birmingham": "GB", "edinburgh": "GB",
    "bristol": "GB", "cambridge": "GB", "oxford": "GB", "glasgow": "GB",
    "leeds": "GB", "reading": "GB",
    # SG
    "singapore": "SG",
    # AE
    "dubai": "AE", "abu dhabi": "AE", "sharjah": "AE",
    # IN
    "bangalore": "IN", "bengaluru": "IN", "mumbai": "IN", "delhi": "IN",
    "new delhi": "IN", "hyderabad": "IN", "chennai": "IN", "pune": "IN",
    "gurgaon": "IN", "gurugram": "IN", "noida": "IN", "kolkata": "IN",
    # CA
    "toronto": "CA", "vancouver": "CA", "montreal": "CA", "ottawa": "CA",
    "calgary": "CA", "waterloo": "CA",
    # AU
    "sydney": "AU", "melbourne": "AU", "brisbane": "AU", "perth": "AU",
    # PL
    "warsaw": "PL", "warszawa": "PL", "krakow": "PL", "kraków": "PL",
    "wroclaw": "PL", "wrocław": "PL", "gdansk": "PL", "gdańsk": "PL",
    "poznan": "PL", "poznań": "PL",
}

# Region-only / ambiguous buckets (task §7/§9) — never fabricate a country.
_REGION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("apac", "APAC"), ("asia pacific", "APAC"),
    ("emea", "EMEA"),
    ("europe", "EUROPE"), ("eu", "EUROPE"),
    ("latam", "LATAM"), ("latin america", "LATAM"),
    ("mena", "MENA"),
    ("north america", "NORTH_AMERICA"),
    ("worldwide", GLOBAL), ("global", GLOBAL), ("anywhere", GLOBAL),
    ("multiple locations", GLOBAL), ("flexible", GLOBAL),
)

_REMOTE_RE = re.compile(r"\b(remote|work from home|wfh|distributed|100% remote|fully remote)\b", re.I)
_HYBRID_RE = re.compile(r"\bhybrid\b", re.I)
_ONSITE_RE = re.compile(r"\b(on-?site|in-?office|office[- ]based)\b", re.I)

# Description evidence patterns (task §11) — deterministic, no AI.
_DESC_LOCATION_RE = re.compile(
    r"(?:location|based in|office|work location|position location|role location)"
    r"\s*[:\-–]\s*([^\n\.]{2,60})", re.I)
_DESC_RESIDENCY_RE = re.compile(
    r"(?:remote within|candidates must (?:reside|be located) in|must be based in|"
    r"applicants? (?:must be )?(?:located|based) in|only (?:open|available) (?:to|in))"
    r"\s*[:\-–]?\s*([^\n\.]{2,60})", re.I)

_WORD = r"(?<![a-z0-9])"


def normalize_country_code(token: str) -> str | None:
    """Any alias/variant → ISO-2 code of the CONFIGURED countries, else None.

    'United Kingdom' / 'UK' / 'U.K.' / 'Great Britain' / 'GB' → 'GB'
    'United Arab Emirates' / 'UAE' / 'U.A.E.' → 'AE'
    """
    t = (token or "").strip().lower()
    if not t:
        return None
    for code, (_name, aliases) in COUNTRY_ALIASES.items():
        if t in aliases:
            return code
    return None


def _code_to_region(code: str | None, region_of=None) -> str | None:
    """ISO code → the region STRING the rest of the pipeline stores
    (jobs.location_region uses names like 'Germany', 'UK', 'UAE')."""
    if code is None:
        return None
    if region_of:
        return region_of(code)
    name = COUNTRY_ALIASES.get(code, (None,))[0]
    if name:
        return "UK" if code == "GB" else name  # classifier string for GB is 'UK'
    return None


@dataclass
class Classification:
    """One job's classification result (task §4 standard output)."""
    country_code: str | None          # ISO-2 of CONFIGURED countries, or None
    country_name: str | None
    region: str                       # 'Germany' / 'UK' / 'APAC' / 'GLOBAL' / 'UNKNOWN'
    city: str | None
    remote_type: str                  # REMOTE / HYBRID / ONSITE / ''
    classification_confidence: str    # HIGH / MEDIUM / LOW / UNKNOWN
    classification_source: str        # SRC_* vocabulary
    classification_reason: str
    supported_countries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "country_code": self.country_code, "country_name": self.country_name,
            "region": self.region, "city": self.city,
            "remote_type": self.remote_type,
            "classification_confidence": self.classification_confidence,
            "classification_source": self.classification_source,
            "classification_reason": self.classification_reason,
            "supported_countries": self.supported_countries,
        }


def _split_locations(location: str) -> list[str]:
    return [p.strip() for p in re.split(r"[,/&/|]| or | and ", location) if p.strip()]


def _find_country_in_text(text: str) -> tuple[str | None, str | None]:
    """First configured country (alias or city) found in free text → (code, city)."""
    t = (text or "").strip().lower()
    if not t:
        return None, None
    for part in _split_locations(t):
        code = normalize_country_code(part)
        if code:
            return code, part
    # word-boundary scan for aliases with punctuation ('U.K.', 'Remote (UK)')
    for code, (_name, aliases) in COUNTRY_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            if re.search(_WORD + re.escape(alias) + r"(?![a-z0-9])", t):
                return code, None
    for city, code in CITY_TO_COUNTRY.items():
        if re.search(_WORD + re.escape(city) + r"(?![a-z0-9])", t):
            return code, city
    return None, None


def _multi_location(location: str) -> list[str]:
    """Distinct configured country codes present in a multi-location string."""
    codes: list[str] = []
    for part in _split_locations((location or "").lower()):
        code = normalize_country_code(part)
        if code is None:
            code = CITY_TO_COUNTRY.get(part)
        if code and code not in codes:
            codes.append(code)
    return codes


def _description_evidence(description: str, work_type: str, region_of=None,
                          remote_type: str | None = None) -> Classification | None:
    """Deterministic description evidence ("Location:", "must reside in …").

    Returns None when the description names no configured country. Used both
    for the general pass (priority 4) and as the fallback when a REMOTE
    location carries no geographic qualifier of its own.
    """
    if not description:
        return None
    for rx in (_DESC_LOCATION_RE, _DESC_RESIDENCY_RE):
        m = rx.search(description)
        if m:
            code, city = _find_country_in_text(m.group(1))
            if code:
                return Classification(
                    code, COUNTRY_ALIASES[code][0],
                    _code_to_region(code, region_of) or code,
                    city, (remote_type or work_type or ONSITE), CONF_MEDIUM,
                    SRC_DESCRIPTION,
                    f"description evidence: '{m.group(0)[:50]}'", [code])
    return None


def classify_job(job: dict, region_of=None) -> Classification:
    """Classify ONE job through the priority chain (deterministic, no AI).

    `job` keys used: location (raw), description, source, country_code /
    structured metadata if present. Idempotent: same inputs → same output.
    """
    location = (job.get("location") or "").strip()
    loc_lower = location.lower()
    description = job.get("description") or ""
    source_hint_code = normalize_country_code(job.get("search_country") or
                                              job.get("source_country") or "")

    # Work type (independent of country answer)
    work_type = UNKNOWN_WORK_TYPE
    if _HYBRID_RE.search(location):
        work_type = HYBRID
    elif _ONSITE_RE.search(location):
        work_type = ONSITE
    elif _REMOTE_RE.search(location):
        work_type = REMOTE

    is_remote = work_type == REMOTE or (not location and True)

    # --- 1. STRUCTURED_COUNTRY: explicit ISO field in the job record -------
    explicit_code = normalize_country_code(job.get("country_code") or "")
    if not explicit_code and job.get("ats_metadata"):
        meta = job.get("ats_metadata") or {}
        explicit_code = normalize_country_code(
            str(meta.get("addressCountry") or meta.get("country") or ""))
        if explicit_code:
            return Classification(
                explicit_code, COUNTRY_ALIASES[explicit_code][0],
                _code_to_region(explicit_code, region_of) or explicit_code,
                None, work_type or ONSITE, CONF_HIGH, SRC_ATS_METADATA,
                "ATS/JobPosting structured country field",
                [explicit_code])

    if explicit_code:
        return Classification(
            explicit_code, COUNTRY_ALIASES[explicit_code][0],
            _code_to_region(explicit_code, region_of) or explicit_code,
            None, work_type, CONF_HIGH, SRC_STRUCTURED_COUNTRY,
            "explicit structured country field", [explicit_code])

    # --- multi-location: "Singapore / London / New York" -------------------
    multi = _multi_location(location)
    if len(multi) > 1:
        primary = multi[0]
        return Classification(
            primary, COUNTRY_ALIASES[primary][0],
            _code_to_region(primary, region_of) or primary,
            None, work_type or ONSITE, CONF_HIGH, SRC_TEXT_LOCATION,
            f"multi-location; primary={primary} supported={multi}",
            multi)

    # --- remote with qualifier ---------------------------------------------
    if is_remote:
        # strip remote keywords to inspect the qualifier
        rest = _REMOTE_RE.sub(" ", location)
        rest = re.sub(r"^[\s\-–,/\(\)\[\]]+|[\s\-–,/\(\)\[\]]+$", "", rest).strip()
        if rest:
            code, city = _find_country_in_text(rest)
            if code:
                # "Remote - Singapore" → SG HIGH; "Remote - India" under an SG
                # search → IN (source hint NEVER overrides text, task §10)
                return Classification(
                    code, COUNTRY_ALIASES[code][0],
                    _code_to_region(code, region_of) or code,
                    city, REMOTE, CONF_HIGH, SRC_TEXT_LOCATION,
                    "remote with explicit country qualifier", [code])
            # Region pattern BEFORE description-residency overrides: a remote job
            # saying "(EU)" is region-constrained even if the description
            # mentions residency in one specific country — the location text is
            # the job's own structured signal; description stays secondary for
            # remote-region roles (conflict detection records it downstream).
            for pat, region in _REGION_PATTERNS:
                if re.search(_WORD + re.escape(pat) + r"(?![a-z0-9])", rest.lower()):
                    return Classification(
                        None, None, region, None, REMOTE, CONF_MEDIUM,
                        SRC_TEXT_LOCATION,
                        f"remote constrained to region {region}", [])
        # No qualifier, or an unresolvable one: the description may still pin a
        # country ("Remote" + "candidates must reside in Germany" → DE).
        desc = _description_evidence(description, work_type, region_of,
                                     remote_type=REMOTE)
        if desc:
            return desc
        if not rest:
            # pure "Remote" / "Anywhere" / empty → region-only bucket
            return Classification(
                None, None, GLOBAL if not location else "UNKNOWN",
                None, REMOTE, CONF_LOW if location else CONF_UNKNOWN,
                SRC_TEXT_LOCATION if location else SRC_UNKNOWN,
                "remote with no geographic qualifier" if location
                else "no location data at all",
                [])
        # remote with unresolvable qualifier and no description evidence
        return Classification(
            None, None, "UNKNOWN", None, REMOTE, CONF_LOW, SRC_UNKNOWN,
            f"remote with unresolvable qualifier '{rest[:40]}'", [])

    # --- 2. TEXT_LOCATION / 3. CITY_MAP on the location itself -------------
    code, city = _find_country_in_text(location)
    if code:
        region = _code_to_region(code, region_of) or code
        if city and city in CITY_TO_COUNTRY:
            return Classification(
                code, COUNTRY_ALIASES[code][0], region, city,
                work_type or ONSITE, CONF_HIGH, SRC_CITY_MAP,
                f"city '{city}' → {code}", [code])
        return Classification(
            code, COUNTRY_ALIASES[code][0], region, None,
            work_type or ONSITE, CONF_HIGH, SRC_TEXT_LOCATION,
            "explicit country in location text", [code])

    # region-only / ambiguous: EMEA / APAC / Europe / Global / Flexible -----
    for pat, region in _REGION_PATTERNS:
        if re.search(_WORD + re.escape(pat) + r"(?![a-z0-9])", loc_lower):
            return Classification(
                None, None, region, None, work_type or ONSITE, CONF_MEDIUM,
                SRC_TEXT_LOCATION, f"region-only location '{location[:40]}'",
                [])

    # --- 4. DESCRIPTION evidence (deterministic patterns) ------------------
    desc = _description_evidence(description, work_type, region_of)
    if desc:
        return desc

    # --- 6. SOURCE_HINT: last deterministic resort, LOW confidence ---------
    if source_hint_code:
        return Classification(
            source_hint_code, COUNTRY_ALIASES[source_hint_code][0],
            _code_to_region(source_hint_code, region_of) or source_hint_code,
            None, work_type or ONSITE, CONF_LOW, SRC_SOURCE_HINT,
            "source search country used as hint only", [source_hint_code])

    # --- 8. UNKNOWN: honest -------------------------------------------------
    return Classification(
        None, None, "UNKNOWN", None, work_type, CONF_UNKNOWN, SRC_UNKNOWN,
        f"insufficient evidence for '{location[:40]}'" if location
        else "no location data", [])


def _ai_prompt(location: str, description: str) -> str:
    codes = ", ".join(sorted(COUNTRY_ALIASES))
    snippet = (description or "")[:600]
    return (
        "Classify this job posting's location into ONE country. Answer with "
        "ONLY compact JSON: {\"country_code\": \"XX\", \"confidence\": "
        "\"HIGH|MEDIUM|LOW\", \"reason\": \"short\"}.\n"
        f"Allowed country_code values: {codes}. If none fits, use null.\n"
        "Never guess: null is the correct answer when the text is ambiguous.\n\n"
        f"LOCATION: {location!r}\n"
        f"DESCRIPTION: {snippet!r}")


async def classify_job_ai(job: dict, ai_client, region_of=None) -> Classification:
    """Priority 7 — bounded LLM fallback, used ONLY for rows the deterministic
    chain left UNKNOWN (semantic residue). Validated: any answer that is not a
    configured country code, or a low-confidence guess on empty evidence, is
    discarded → honest UNKNOWN. One job per call (bounded prompt/output).
    """
    location = (job.get("location") or "").strip()
    description = job.get("description") or ""
    work_type = UNKNOWN_WORK_TYPE
    if _HYBRID_RE.search(location):
        work_type = HYBRID
    elif _ONSITE_RE.search(location):
        work_type = ONSITE
    elif _REMOTE_RE.search(location):
        work_type = REMOTE

    unknown = Classification(
        None, None, "UNKNOWN", None, work_type, CONF_UNKNOWN, SRC_UNKNOWN,
        f"AI fallback declined for '{location[:40]}'" if location
        else "no location data", [])
    if not location and not description:
        return unknown
    try:
        from app.ai_client import parse_json_response
        raw = await ai_client.chat(_ai_prompt(location, description),
                                   max_tokens=120, timeout=20.0)
        parsed = parse_json_response(raw)
    except Exception as exc:  # noqa: BLE001 — AI must never break classify
        logger.warning("classification: AI fallback failed (%s)", exc)
        return unknown
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else None
    if not isinstance(parsed, dict):
        return unknown
    code = normalize_country_code(str(parsed.get("country_code") or ""))
    if not code:
        return unknown
    try:
        conf = float({"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.3}.get(
            str(parsed.get("confidence") or "").upper(), 0.3))
    except (TypeError, ValueError):
        conf = 0.3
    if conf < 0.5:
        # a low-confidence AI guess is not evidence — stay honest
        return unknown
    return Classification(
        code, COUNTRY_ALIASES[code][0],
        _code_to_region(code, region_of) or code, None,
        work_type or ONSITE, CONF_MEDIUM, SRC_AI_FALLBACK,
        f"AI fallback: {str(parsed.get('reason') or '')[:60]}", [code])


def detect_conflict(job: dict, result: Classification) -> str | None:
    """Return a conflict description when evidence disagrees (task §15).

    Rule: structured/text location wins; a DIFFERENT configured country found
    anywhere in the description's location-evidence lines is recorded as a
    conflict, never silently applied. Scans the whole description for
    configured-country mentions near location markers, so 'Location: Kuala
    Lumpur office' conflicts with a Singapore structured location even
    though Malaysia itself is not a configured target.
    """
    if not result.country_code or not job.get("description"):
        return None
    desc = job["description"]
    # 1) location-evidence lines (strong signal)
    for rx in (_DESC_LOCATION_RE, _DESC_RESIDENCY_RE):
        m = rx.search(desc)
        if m:
            code, _city = _find_country_in_text(m.group(1))
            if code and code != result.country_code:
                return (f"conflict: location says {result.country_code}, "
                        f"description says {code} (kept {result.country_code})")
    # 2) unconfigured-country mention near a location marker (Kuala Lumpur…)
    m = _DESC_LOCATION_RE.search(desc)
    if m and not _find_country_in_text(m.group(1))[0]:
        # the evidence line names a place that maps to NO configured country
        # while the job is classified somewhere else → suspicious, record it
        snippet = m.group(1).strip()[:40]
        return (f"conflict: location says {result.country_code}, "
                f"description location '{snippet}' is outside configured "
                f"countries (kept {result.country_code})")
    return None
