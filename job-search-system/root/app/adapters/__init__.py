"""M4: adapters package — JobSourceAdapter implementations (Golden Rule 9).

ALL_ADAPTERS is the discovery registry the orchestrator runs. Adding a source
= implement JobSourceAdapter + add it here. Nothing else changes.

Order: ATS boards first (M4 discipline), then keyed multi-country metasearch
(jooble/adzuna — silent no-ops until keys are configured), then the
country-scoped legacy boards.

Registering keyed adapters is safe: without keys they return
SOURCE_FAILURE with a clear error string — visible in discovery telemetry,
never a crash, never a lowered bar.
"""

from app.adapters.greenhouse_facade import GreenhouseAdapter
from app.adapters.lever import LeverAdapter
from app.adapters.ashby import AshbyAdapter
from app.adapters.smartrecruiters import SmartRecruitersAdapter
from app.adapters.jooble import JoobleAdapter
from app.adapters.adzuna import AdzunaAdapter
from app.adapters.reed import ReedAdapter
from app.adapters.country_scoped import (
    ArbeitnowAdapter,
    RemotiveAdapter,
    JobicyAdapter,
    WeWorkRemotelyAdapter,
    RemoteOKAdapter,
    HimalayasAdapter,
    FourDayWeekAdapter,
    LandingJobsAdapter,
    RecruiteeAdapter,
    MyCareersFutureAdapter,
    WellfoundAdapter,
    WorkingNomadsAdapter,
)

ALL_ADAPTERS = [
    GreenhouseAdapter,
    LeverAdapter,
    AshbyAdapter,
    SmartRecruitersAdapter,
    JoobleAdapter,
    AdzunaAdapter,
    ReedAdapter,
    ArbeitnowAdapter,
    RemotiveAdapter,
    JobicyAdapter,
    WeWorkRemotelyAdapter,
    RemoteOKAdapter,
    HimalayasAdapter,
    FourDayWeekAdapter,
    LandingJobsAdapter,
    RecruiteeAdapter,
    MyCareersFutureAdapter,
    WellfoundAdapter,
    WorkingNomadsAdapter,
]
