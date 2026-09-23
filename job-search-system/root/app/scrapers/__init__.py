from app.scrapers.hackernews import HackerNewsScraper
from app.scrapers.remotive import RemotiveScraper
from app.scrapers.usajobs import USAJobsScraper
from app.scrapers.linkedin import LinkedInScraper
from app.scrapers.dice import DiceScraper
from app.scrapers.arbeitnow import ArbeitnowScraper
from app.scrapers.jobicy import JobicyScraper
from app.scrapers.indeed import IndeedScraper
from app.scrapers.remoteok import RemoteOKScraper
from app.scrapers.himalayas import HimalayasScraper
from app.scrapers.wellfound import WellfoundScraper
from app.scrapers.builtin import BuiltInScraper
from app.scrapers.greenhouse import GreenhouseScraper
from app.scrapers.adzuna import AdzunaScraper
# NOTE: WeWorkRemotelyScraper was implemented but never registered, so it
# never ran. Registered here (verified live 2026-09-23).
from app.scrapers.weworkremotely import WeWorkRemotelyScraper
from app.scrapers.workingnomads import WorkingNomadsScraper
from app.scrapers.recruitee import RecruiteeScraper
from app.scrapers.mycareersfuture import MyCareersFutureScraper
from app.scrapers.ashby import AshbyScraper
from app.scrapers.landingjobs import LandingJobsScraper
from app.scrapers.fourdayweek import FourDayWeekScraper

ALL_SCRAPERS = [
    HackerNewsScraper, RemotiveScraper, USAJobsScraper,
    LinkedInScraper, DiceScraper,
    ArbeitnowScraper, JobicyScraper, IndeedScraper,
    RemoteOKScraper, HimalayasScraper,
    WellfoundScraper, BuiltInScraper,
    GreenhouseScraper, AdzunaScraper,
    # Added 2026-09-23 (coverage expansion)
    WeWorkRemotelyScraper,      # global remote (RSS) — was orphaned
    WorkingNomadsScraper,       # global remote (keyless JSON)
    RecruiteeScraper,           # EU ATS boards (keyless JSON)
    MyCareersFutureScraper,     # Singapore government board (keyless JSON)
    AshbyScraper,               # ATS boards (keyless JSON + real salaries)
    LandingJobsScraper,         # EU tech board (keyless JSON)
    FourDayWeekScraper,         # remote / 4-day-week board (keyless JSON)
]
