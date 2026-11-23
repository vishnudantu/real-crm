"""NOAA solar position algorithm — pure Python, deterministic, no network.

Reference
---------
NOAA Solar Calculator (Earth System Research Laboratory).
Algorithm: "Solar Position Algorithm for Solar Radiation Applications"
(``https://www.esrl.noaa.gov/gmd/grad/solcalc/``).

The implementation follows the simplified fractional-year formulation used by
NOAA's online calculator. Accuracy is ±1-2 minutes for sunrise/sunset at
mid-latitudes, which is sufficient for real-estate fact-sheet content.

All functions accept *timezone-aware* ``datetime`` objects. Naive datetimes
raise ``ValueError`` to prevent silent UTC assumptions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Protocol, runtime_checkable

__all__ = [
    "SolarPosition",
    "SunTimes",
    "SolarProvider",
    "NoOpProvider",
    "solar_position",
    "sun_times",
    "get_provider",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SolarPosition:
    """Instantaneous solar position at a given time."""

    elevation: float  # degrees above horizon
    azimuth: float  # degrees clockwise from north


@dataclass(frozen=True)
class SunTimes:
    """Sunrise, sunset, solar noon, and day length for one date."""

    date: date
    sunrise: datetime
    sunset: datetime
    solar_noon: datetime
    day_length: timedelta


# ---------------------------------------------------------------------------
# Optional external provider protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SolarProvider(Protocol):
    """Optional pluggable provider for tenants that supply an external API."""

    def sun_times(self, latitude: float, longitude: float, when: date) -> SunTimes:
        """Return sunrise/sunset/noon/day-length for the given date."""
        ...

    def solar_position(self, latitude: float, longitude: float, when: datetime) -> SolarPosition:
        """Return elevation/azimuth at the given instant."""
        ...


class NoOpProvider:
    """Default no-op provider — the built-in algorithm is always used instead."""

    def sun_times(self, latitude: float, longitude: float, when: date) -> SunTimes:
        raise NotImplementedError("External provider not configured.")

    def solar_position(self, latitude: float, longitude: float, when: datetime) -> SolarPosition:
        raise NotImplementedError("External provider not configured.")


def get_provider() -> SolarProvider | NoOpProvider:
    """Return the active provider. Built-in is the default."""
    return NoOpProvider()


# ---------------------------------------------------------------------------
# Core NOAA math (internal helpers)
# ---------------------------------------------------------------------------


def _ensure_aware(dt: datetime) -> datetime:
    """Raise if *dt* is timezone-naive; otherwise return it unchanged."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError("datetime must be timezone-aware")
    return dt


def _fractional_year(when: datetime) -> float:
    """Return the fractional year γ in radians (NOAA eq. 1)."""
    day_of_year = when.timetuple().tm_yday
    hour = when.hour + when.minute / 60.0 + when.second / 3600.0
    # For 24-hour calculation NOAA uses hour in [0,24). We use 12 (noon) when
    # computing daily events; for instantaneous position we use the actual hour.
    gamma = (2 * math.pi / 365) * (day_of_year - 1 + (hour - 12) / 24)
    return gamma


def _equation_of_time(gamma: float) -> float:
    """Equation of time in minutes (NOAA eq. 2)."""
    return 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )


def _solar_declination(gamma: float) -> float:
    """Solar declination δ in radians (NOAA eq. 3)."""
    return (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )


def _hour_angle_sunrise(latitude: float, declination: float) -> float:
    """Sunrise hour angle ω₀ in radians (NOAA eq. 5).

    Returns the angle for the *upper limb* (zenith = 90.833°) which accounts
    for atmospheric refraction and the solar disc's semi-diameter.
    """
    lat_rad = math.radians(latitude)
    cos_omega = (
        math.cos(math.radians(90.833))
        / (math.cos(lat_rad) * math.cos(declination))
        - math.tan(lat_rad) * math.tan(declination)
    )
    # Clamp to [-1, 1] to avoid domain errors at high latitudes.
    cos_omega = max(-1.0, min(1.0, cos_omega))
    return math.acos(cos_omega)


def _utc_offset_hours(when: datetime) -> float:
    """Return the UTC offset of the given timezone-aware datetime in hours."""
    offset = when.utcoffset()
    if offset is None:
        raise ValueError("datetime must have a UTC offset")
    return offset.total_seconds() / 3600.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def solar_position(
    latitude: float,
    longitude: float,
    when: datetime,
) -> SolarPosition:
    """Compute solar elevation and azimuth at an instant.

    Parameters
    ----------
    latitude : float
        Degrees north (-90 to +90).
    longitude : float
        Degrees east (-180 to +180).
    when : datetime
        Timezone-aware datetime.

    Returns
    -------
    SolarPosition
        ``elevation`` (degrees above horizon) and ``azimuth`` (degrees
        clockwise from north, 0-360).
    """
    _ensure_aware(when)

    gamma = _fractional_year(when)
    eq_time = _equation_of_time(gamma)  # minutes
    decl = _solar_declination(gamma)  # radians

    utc_offset = _utc_offset_hours(when)
    # True solar time in minutes.
    true_solar_time = (
        when.hour * 60 + when.minute + when.second / 60.0
        + eq_time
        + 4 * longitude
        - 60 * utc_offset
    ) % 1440

    # Hour angle in degrees (negative = morning, positive = afternoon).
    if true_solar_time / 4 < 0:
        ha_deg = true_solar_time / 4 + 180
    else:
        ha_deg = true_solar_time / 4 - 180
    ha_rad = math.radians(ha_deg)

    lat_rad = math.radians(latitude)

    # Solar zenith angle (NOAA eq. 6).
    cos_zenith = (
        math.sin(lat_rad) * math.sin(decl)
        + math.cos(lat_rad) * math.cos(decl) * math.cos(ha_rad)
    )
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    zenith = math.acos(cos_zenith)
    elevation = 90.0 - math.degrees(zenith)

    # Solar azimuth angle (NOAA eq. 7).
    az_denom = math.cos(lat_rad) * math.sin(zenith)
    if abs(az_denom) < 1e-12:
        # Sun directly overhead — azimuth is undefined; default to 180°.
        azimuth = 180.0
    else:
        cos_az = (
            -(math.sin(lat_rad) * cos_zenith - math.sin(decl))
            / az_denom
        )
        cos_az = max(-1.0, min(1.0, cos_az))
        az_rad = math.acos(cos_az)
        azimuth = math.degrees(az_rad)
        if ha_rad > 0:
            azimuth = 360.0 - azimuth

    return SolarPosition(elevation=elevation, azimuth=azimuth)


def sun_times(
    latitude: float,
    longitude: float,
    when: date | datetime,
) -> SunTimes:
    """Compute sunrise, sunset, solar noon, and day length for a date.

    Parameters
    ----------
    latitude : float
        Degrees north (-90 to +90).
    longitude : float
        Degrees east (-180 to +180).
    when : date or datetime
        The date (or a datetime whose date is used). If a datetime is
        provided its timezone is used for the returned times; otherwise
        UTC is assumed.

    Returns
    -------
    SunTimes
        All datetimes are timezone-aware.
    """
    if isinstance(when, datetime):
        tz = when.tzinfo or UTC
        target_date = when.date() if hasattr(when, "date") else when
        _ensure_aware(when)
    else:
        tz = UTC
        target_date = when

    # Use noon on the target date in the given timezone for the γ calculation.
    noon_local = datetime(
        target_date.year, target_date.month, target_date.day, 12, 0, 0, tzinfo=tz
    )
    gamma = _fractional_year(noon_local)
    eq_time = _equation_of_time(gamma)  # minutes
    decl = _solar_declination(gamma)  # radians

    omega = _hour_angle_sunrise(latitude, decl)  # radians
    omega_deg = math.degrees(omega)

    utc_offset = _utc_offset_hours(noon_local)

    # Solar noon in local minutes from midnight (NOAA eq. 9).
    solar_noon_min = (
        720 - 4 * longitude - eq_time + utc_offset * 60
    ) % 1440

    # Sunrise and sunset in local minutes from midnight (NOAA eq. 8).
    sunrise_min = solar_noon_min - omega_deg * 4
    sunset_min = solar_noon_min + omega_deg * 4

    def _minutes_to_datetime(minutes: float) -> datetime:
        hours = int(minutes // 60) % 24
        mins = int(minutes % 60)
        secs = int((minutes % 1) * 60)
        return datetime(
            target_date.year, target_date.month, target_date.day,
            hours, mins, secs, tzinfo=tz,
        )

    sunrise_dt = _minutes_to_datetime(sunrise_min)
    sunset_dt = _minutes_to_datetime(sunset_min)
    noon_dt = _minutes_to_datetime(solar_noon_min)
    day_length = timedelta(minutes=sunset_min - sunrise_min)

    return SunTimes(
        date=target_date,
        sunrise=sunrise_dt,
        sunset=sunset_dt,
        solar_noon=noon_dt,
        day_length=day_length,
    )
