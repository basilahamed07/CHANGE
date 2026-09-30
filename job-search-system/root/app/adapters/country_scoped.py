"""Country-scoped adapters over the legacy M4-era keyless scrapers.

Nine existing scrapers had scrapers without country scoping — they ingested
into whatever region the scheduler allowed. This module wraps each one in the
shared CountryScopedAdapter so the discovery orchestrator can point them at
ANY enabled country: Germany, India, Canada, Australia, Poland, etc.

Remote boards (remotive/jobicy/weworkremotely/remoteok/himalayas/4dayweek)
serve geography via their location strings — the facade filters listings to
the target country, and listings that match no enabled country ("Anywhere")
survive only for Remote (which is always allowed). Country boards
(arbeitnow→Germany, landingjobs→EU, recruitee→EU) get real geographic reach.

Each adapter is 2 lines of real logic + the shared facade contract
(never raises, honest stop-reasons, CanonicalJob normalization).
"""

from __future__ import annotations

from app.adapters.country_facade import CountryScopedAdapter
from app.scrapers.arbeitnow import ArbeitnowScraper
from app.scrapers.remotive import RemotiveScraper
from app.scrapers.jobicy import JobicyScraper
from app.scrapers.weworkremotely import WeWorkRemotelyScraper
from app.scrapers.remoteok import RemoteOKScraper
from app.scrapers.himalayas import HimalayasScraper
from app.scrapers.fourdayweek import FourDayWeekScraper
from app.scrapers.landingjobs import LandingJobsScraper
from app.scrapers.recruitee import RecruiteeScraper
from app.scrapers.mycareersfuture import MyCareersFutureScraper
from app.scrapers.wellfound import WellfoundScraper
from app.scrapers.workingnomads import WorkingNomadsScraper
from app.scrapers.builtin import BuiltInScraper


class ArbeitnowAdapter(CountryScopedAdapter):
    """Germany-native job board (API feed) — strongest for Germany; also
    carries EU remote roles that classify to other EU countries."""
    source_name = "arbeitnow"
    scraper_cls = ArbeitnowScraper


class RemotiveAdapter(CountryScopedAdapter):
    """Remote board with per-country candidate-location strings
    ('candidate_required_location' — e.g. 'Germany', 'Canada', 'Worldwide')."""
    source_name = "remotive"
    scraper_cls = RemotiveScraper


class JobicyAdapter(CountryScopedAdapter):
    """Remote board with jobGeo strings ('Europe', 'UK', 'Canada', 'USA'…)."""
    source_name = "jobicy"
    scraper_cls = JobicyScraper


class WeWorkRemotelyAdapter(CountryScopedAdapter):
    """RSS feeds (devops + backend categories); region text lives in titles/
    descriptions. Weakest geographic signal — facade filter + region gate."""
    source_name = "weworkremotely"
    scraper_cls = WeWorkRemotelyScraper


class RemoteOKAdapter(CountryScopedAdapter):
    source_name = "remoteok"
    scraper_cls = RemoteOKScraper


class HimalayasAdapter(CountryScopedAdapter):
    source_name = "himalayas"
    scraper_cls = HimalayasScraper


class FourDayWeekAdapter(CountryScopedAdapter):
    source_name = "4dayweek"
    scraper_cls = FourDayWeekScraper


class LandingJobsAdapter(CountryScopedAdapter):
    """EU-weighted tech board (PT/ES/DE/NL + remote-EU) with structured
    {city, country_code} locations."""
    source_name = "landingjobs"
    scraper_cls = LandingJobsScraper


class RecruiteeAdapter(CountryScopedAdapter):
    """EU-heavy per-company ATS boards (bunq/Adyen/Picnic… = Netherlands
    strength); company list overridable via 'recruitee_companies' key."""
    source_name = "recruitee"
    scraper_cls = RecruiteeScraper


class BuiltinAdapter(CountryScopedAdapter):
    """Built In tech-city boards (US + Canada: Toronto/Vancouver/Calgary —
    real CA coverage the country sweep exposed as missing). Scraper existed
    since M1 but was NEVER wired into discovery (found by the Stage-1 audit).
    keyless; multi-city listing locations."""
    source_name = "builtin"
    scraper_cls = BuiltInScraper


class MyCareersFutureAdapter(CountryScopedAdapter):
    """Singapore's government board (#1 SG portal; every EP role must post
    there 14 days before anywhere else). Singapore-only by definition —
    region_hint skips other countries with an honest empty pass."""
    source_name = "mycareersfuture"
    scraper_cls = MyCareersFutureScraper
    region_hint = "Singapore"


class WellfoundAdapter(CountryScopedAdapter):
    """Startup board (AngelList) — global startup scene with strong India,
    UK, NL coverage. Region text lives in listing locations (varied formats)."""
    source_name = "wellfound"
    scraper_cls = WellfoundScraper


class WorkingNomadsAdapter(CountryScopedAdapter):
    """Global remote board (keyless JSON feed) — country text in locations."""
    source_name = "workingnomads"
    scraper_cls = WorkingNomadsScraper
