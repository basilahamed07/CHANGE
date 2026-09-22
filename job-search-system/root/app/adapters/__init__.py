"""M4: adapters package — JobSourceAdapter implementations (Golden Rule 9).

ALL_ADAPTERS is the discovery registry the orchestrator runs. Adding a source
= implement JobSourceAdapter + add it here. Nothing else changes.
"""

from app.adapters.greenhouse_facade import GreenhouseAdapter
from app.adapters.lever import LeverAdapter
from app.adapters.ashby import AshbyAdapter
from app.adapters.smartrecruiters import SmartRecruitersAdapter

ALL_ADAPTERS = [
    GreenhouseAdapter,
    LeverAdapter,
    AshbyAdapter,
    SmartRecruitersAdapter,
]
