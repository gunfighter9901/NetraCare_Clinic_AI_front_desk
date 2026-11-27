from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.config import get_settings


class ClinicClock:
    def now(self) -> datetime:
        raise NotImplementedError


@dataclass(frozen=True)
class FixedClock(ClinicClock):
    fixed_now: datetime

    def now(self) -> datetime:
        return self.fixed_now


@dataclass(frozen=True)
class SystemClock(ClinicClock):
    timezone: str

    def now(self) -> datetime:
        return datetime.now(ZoneInfo(self.timezone)).replace(tzinfo=None)


@lru_cache
def get_clock() -> ClinicClock:
    settings = get_settings()
    if settings.clinic_now is not None:
        return FixedClock(settings.clinic_now.replace(tzinfo=None))
    return SystemClock(settings.clinic_timezone)
