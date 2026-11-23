"""Unit tests for the NOAA solar position engine."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from app.modules.solar.engine import (
    NoOpProvider,
    SolarPosition,
    SunTimes,
    get_provider,
    solar_position,
    sun_times,
)


# Hyderabad: 17.38°N, 78.48°E
_HYD_LAT = 17.38
_HYD_LNG = 78.48
_IST = timezone(timedelta(hours=5, minutes=30))


class TestSunTimes:
    """Tests for sunrise/sunset/solar-noon computation."""

    def test_hyderabad_vernal_equinox(self) -> None:
        """Hyderabad on 2026-03-20 (vernal equinox).

        Expected approximate values (IST = UTC+5:30):
        - Sunrise: ~06:15 IST
        - Sunset: ~18:22 IST
        - Solar noon: ~12:19 IST
        - Day length: ~12.1 hours
        """
        target = date(2026, 3, 20)
        st = sun_times(_HYD_LAT, _HYD_LNG, target)
        assert st.date == target
        # Sunrise should be between 05:30 and 07:00 IST.
        sunrise_ist = st.sunrise.astimezone(_IST)
        assert 5 <= sunrise_ist.hour <= 7, f"Unexpected sunrise: {sunrise_ist}"
        # Sunset should be between 17:30 and 19:30 IST.
        sunset_ist = st.sunset.astimezone(_IST)
        assert 17 <= sunset_ist.hour <= 19, f"Unexpected sunset: {sunset_ist}"
        # Day length should be approximately 12 hours.
        hours = st.day_length.total_seconds() / 3600
        assert 11.5 <= hours <= 12.5, f"Unexpected day length: {hours}"
        # Solar noon should be between 11:30 and 13:00 IST.
        noon_ist = st.solar_noon.astimezone(_IST)
        assert 11 <= noon_ist.hour <= 13, f"Unexpected solar noon: {noon_ist}"

    def test_summer_solstice_longer_day(self) -> None:
        """Summer solstice should have a longer day than winter solstice."""
        summer = sun_times(_HYD_LAT, _HYD_LNG, date(2026, 6, 21))
        winter = sun_times(_HYD_LAT, _HYD_LNG, date(2026, 12, 21))
        assert summer.day_length > winter.day_length

    def test_returns_sun_times_dataclass(self) -> None:
        st = sun_times(_HYD_LAT, _HYD_LNG, date(2026, 3, 20))
        assert isinstance(st, SunTimes)
        assert st.sunrise.tzinfo is not None
        assert st.sunset.tzinfo is not None
        assert st.solar_noon.tzinfo is not None

    def test_timezone_aware_datetime_input(self) -> None:
        """When a datetime is passed, its timezone is used for output."""
        dt = datetime(2026, 3, 20, 12, 0, tzinfo=_IST)
        st = sun_times(_HYD_LAT, _HYD_LNG, dt)
        assert st.sunrise.tzinfo == _IST


class TestSolarPosition:
    """Tests for instantaneous solar elevation/azimuth."""

    def test_noon_elevation_high(self) -> None:
        """At solar noon (~12:19 IST = ~06:49 UTC), elevation should be high."""
        # Solar noon for Hyderabad on equinox is approximately 06:49 UTC.
        solar_noon_utc = datetime(2026, 3, 20, 6, 49, tzinfo=UTC)
        pos = solar_position(_HYD_LAT, _HYD_LNG, solar_noon_utc)
        assert isinstance(pos, SolarPosition)
        assert pos.elevation > 60, f"Expected high noon elevation, got {pos.elevation}"

    def test_morning_east_azimuth(self) -> None:
        """In the morning, azimuth should be roughly east (90°)."""
        morning = datetime(2026, 3, 20, 6, 0, tzinfo=UTC)
        pos = solar_position(_HYD_LAT, _HYD_LNG, morning)
        # Azimuth should be in the eastern half (0-180).
        assert 0 <= pos.azimuth <= 180

    def test_afternoon_west_azimuth(self) -> None:
        """In the afternoon, azimuth should be roughly west (270°)."""
        afternoon = datetime(2026, 3, 20, 18, 0, tzinfo=UTC)
        pos = solar_position(_HYD_LAT, _HYD_LNG, afternoon)
        # Azimuth should be in the western half (180-360).
        assert 180 <= pos.azimuth <= 360

    def test_naive_datetime_raises(self) -> None:
        """Naive datetime must raise ValueError."""
        with pytest.raises(ValueError, match="timezone-aware"):
            solar_position(_HYD_LAT, _HYD_LNG, datetime(2026, 3, 20, 12, 0))


class TestProvider:
    """Tests for the optional external provider interface."""

    def test_default_provider_is_noop(self) -> None:
        provider = get_provider()
        assert isinstance(provider, NoOpProvider)

    def test_noop_provider_raises(self) -> None:
        provider = NoOpProvider()
        with pytest.raises(NotImplementedError):
            provider.sun_times(_HYD_LAT, _HYD_LNG, date(2026, 3, 20))
        with pytest.raises(NotImplementedError):
            provider.solar_position(
                _HYD_LAT, _HYD_LNG, datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
            )
