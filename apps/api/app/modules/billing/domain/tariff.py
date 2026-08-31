from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from .errors import BandNotFound, InvalidRate, TariffCoverageError

ALL_WEEKDAYS = frozenset(range(7))
MINUTES_IN_DAY = 24 * 60


@dataclass(frozen=True, slots=True)
class TariffWindow:
    """A half-open local-time interval, `[start_minute, end_minute)`, on given weekdays.

    Windows never wrap past midnight. A night band is expressed as two windows,
    which keeps coverage validation a simple interval tiling check.
    """

    start_minute: int
    end_minute: int
    weekdays: frozenset[int] = ALL_WEEKDAYS

    def __post_init__(self) -> None:
        if not 0 <= self.start_minute < MINUTES_IN_DAY:
            raise TariffCoverageError(f"start_minute out of range: {self.start_minute}")
        if not 0 < self.end_minute <= MINUTES_IN_DAY:
            raise TariffCoverageError(f"end_minute out of range: {self.end_minute}")
        if self.start_minute >= self.end_minute:
            raise TariffCoverageError(
                f"window does not advance: {self.start_minute} >= {self.end_minute}"
            )
        if not self.weekdays or not self.weekdays <= ALL_WEEKDAYS:
            raise TariffCoverageError(f"invalid weekdays: {sorted(self.weekdays)}")

    def covers(self, weekday: int, minute_of_day: int) -> bool:
        return (
            weekday in self.weekdays
            and self.start_minute <= minute_of_day < self.end_minute
        )


@dataclass(frozen=True, slots=True)
class TariffBand:
    code: str
    rate_cents_per_kwh: int
    windows: tuple[TariffWindow, ...]

    def __post_init__(self) -> None:
        if self.rate_cents_per_kwh < 0:
            raise InvalidRate(f"negative rate for band {self.code}")
        if not self.windows:
            raise TariffCoverageError(f"band {self.code} has no windows")

    def covers(self, weekday: int, minute_of_day: int) -> bool:
        return any(window.covers(weekday, minute_of_day) for window in self.windows)


@dataclass(frozen=True, slots=True)
class TariffSnapshot:
    """An immutable, versioned tariff.

    Bands must tile every minute of every weekday exactly once. A tariff with a
    gap would silently drop a charging session from the bill; a tariff with an
    overlap would make the applied rate depend on band ordering. Both are
    rejected at construction, so an invalid tariff can never reach a close.
    """

    name: str
    timezone: str
    bands: tuple[TariffBand, ...]

    def __post_init__(self) -> None:
        if not self.bands:
            raise TariffCoverageError("tariff has no bands")
        if len({band.code for band in self.bands}) != len(self.bands):
            raise TariffCoverageError("duplicate band code")
        self._validate_coverage()

    def _validate_coverage(self) -> None:
        for weekday in sorted(ALL_WEEKDAYS):
            intervals = sorted(
                (window.start_minute, window.end_minute, band.code)
                for band in self.bands
                for window in band.windows
                if weekday in window.weekdays
            )
            cursor = 0
            for start, end, code in intervals:
                if start > cursor:
                    raise TariffCoverageError(
                        f"weekday {weekday} uncovered between minute {cursor} and {start}"
                    )
                if start < cursor:
                    raise TariffCoverageError(
                        f"weekday {weekday} overlaps at minute {start} in band {code}"
                    )
                cursor = end
            if cursor != MINUTES_IN_DAY:
                raise TariffCoverageError(
                    f"weekday {weekday} uncovered between minute {cursor} and {MINUTES_IN_DAY}"
                )

    def band_for(self, code: str) -> TariffBand:
        for band in self.bands:
            if band.code == code:
                return band
        raise BandNotFound(code)

    def resolve_band(self, moment: datetime) -> TariffBand:
        """Resolve the band that applies to an instant.

        The instant is converted to the tariff's local timezone, because bands are
        defined in the site's wall clock. Callers pass the session's start; a
        session is billed entirely in the band it started in.
        """
        local = moment.astimezone(ZoneInfo(self.timezone))
        minute_of_day = local.hour * 60 + local.minute
        for band in self.bands:
            if band.covers(local.weekday(), minute_of_day):
                return band
        raise BandNotFound(f"{local.weekday()}:{minute_of_day}")
