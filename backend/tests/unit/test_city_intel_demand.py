"""Unit tests for catchment demand aggregation (pure logic, no database)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.city_intel.demand import (
    DEFAULT_PRICE_BANDS,
    UNKNOWN,
    PriceBand,
    aggregate_demand,
    price_band_for,
)

_LAKH = 100_000  # paise
_CRORE = 10_000_000  # paise


@dataclass(frozen=True)
class FakeProject:
    id: UUID
    name: str
    location: str


@dataclass(frozen=True)
class FakeLead:
    project_id: UUID
    status: str = "NEW"
    source: str = "WEBSITE"
    budget_min: int | None = None
    budget_max: int | None = None
    preferred_configuration: str | None = None
    created_at: datetime = datetime(2026, 1, 1)


@dataclass(frozen=True)
class FakeBooking:
    project_id: UUID
    consideration_paise: int
    booked_on: date = date(2026, 1, 15)


def _lead(
    project_id: UUID,
    *,
    budget_min: int | None = None,
    budget_max: int | None = None,
    config: str | None = None,
) -> FakeLead:
    return FakeLead(
        project_id=project_id,
        budget_min=budget_min,
        budget_max=budget_max,
        preferred_configuration=config,
    )


class TestPriceBandFor:
    """Boundary behaviour of ``price_band_for``."""

    def test_exact_minimum_is_inclusive(self) -> None:
        assert price_band_for(0) == "<50L"
        assert price_band_for(5_000_001) == "50L-1Cr"
        assert price_band_for(10_000_001) == "1-2Cr"
        assert price_band_for(20_000_001) == ">2Cr"

    def test_exact_maximum_is_inclusive(self) -> None:
        assert price_band_for(5_000_000) == "<50L"
        assert price_band_for(10_000_000) == "50L-1Cr"
        assert price_band_for(20_000_000) == "1-2Cr"

    def test_value_inside_band(self) -> None:
        assert price_band_for(3 * _CRORE) == ">2Cr"
        assert price_band_for(75 * _LAKH) == "50L-1Cr"

    def test_negative_returns_unknown(self) -> None:
        assert price_band_for(-1) == UNKNOWN

    def test_above_all_bands_returns_unknown(self) -> None:
        assert price_band_for(10**18 + 1) == UNKNOWN

    def test_custom_bands_are_honoured(self) -> None:
        bands = (PriceBand("LOW", 0, 100), PriceBand("HIGH", 101, 1_000))
        assert price_band_for(100, bands) == "LOW"
        assert price_band_for(101, bands) == "HIGH"


class TestAggregateDemandEmpty:
    def test_no_projects_returns_empty_list(self) -> None:
        assert aggregate_demand(projects=[], leads=[], bookings=[]) == []

    def test_project_without_leads_is_zeroed(self) -> None:
        project = FakeProject(uuid4(), "Palm Grove", "Kondapur")

        (demand,) = aggregate_demand(projects=[project], leads=[], bookings=[])

        assert demand.project_id == str(project.id)
        assert demand.locality == "Kondapur"
        assert demand.project_name == "Palm Grove"
        assert demand.lead_count == 0
        assert demand.booking_count == 0
        assert demand.conversion_pct == 0.0
        assert demand.median_budget_paise is None
        assert demand.top_price_band == UNKNOWN
        assert demand.top_property_type == UNKNOWN


class TestConversionAndCounts:
    def test_conversion_percentage_from_bookings_and_leads(self) -> None:
        project = FakeProject(uuid4(), "Palm Grove", "Kondapur")
        leads = [_lead(project.id) for _ in range(4)]
        bookings = [
            FakeBooking(project.id, consideration_paise=6 * _CRORE)
            for _ in range(1)
        ]

        (demand,) = aggregate_demand(projects=[project], leads=leads, bookings=bookings)

        assert demand.lead_count == 4
        assert demand.booking_count == 1
        assert demand.conversion_pct == 25.0

    def test_conversion_is_zero_when_no_leads(self) -> None:
        project = FakeProject(uuid4(), "Palm Grove", "Kondapur")
        bookings = [FakeBooking(project.id, consideration_paise=6 * _CRORE)]

        (demand,) = aggregate_demand(projects=[project], leads=[], bookings=bookings)

        assert demand.booking_count == 1
        assert demand.conversion_pct == 0.0


class TestMedianBudget:
    def test_median_of_odd_number_of_midpoints(self) -> None:
        project = FakeProject(uuid4(), "Palm Grove", "Kondapur")
        leads = [
            _lead(project.id, budget_min=50 * _LAKH, budget_max=50 * _LAKH),
            _lead(project.id, budget_min=100 * _LAKH, budget_max=100 * _LAKH),
            _lead(project.id, budget_min=200 * _LAKH, budget_max=200 * _LAKH),
        ]

        (demand,) = aggregate_demand(projects=[project], leads=leads, bookings=[])

        assert demand.median_budget_paise == 100 * _LAKH

    def test_median_of_even_number_of_midpoints(self) -> None:
        project = FakeProject(uuid4(), "Palm Grove", "Kondapur")
        leads = [
            _lead(project.id, budget_min=10 * _LAKH, budget_max=10 * _LAKH),
            _lead(project.id, budget_min=20 * _LAKH, budget_max=20 * _LAKH),
            _lead(project.id, budget_min=30 * _LAKH, budget_max=30 * _LAKH),
            _lead(project.id, budget_min=40 * _LAKH, budget_max=40 * _LAKH),
        ]

        (demand,) = aggregate_demand(projects=[project], leads=leads, bookings=[])

        assert demand.median_budget_paise == 25 * _LAKH

    def test_midpoint_from_partial_budget_range(self) -> None:
        project = FakeProject(uuid4(), "Palm Grove", "Kondapur")
        leads = [
            _lead(project.id, budget_min=40 * _LAKH, budget_max=60 * _LAKH),
            _lead(project.id, budget_min=None, budget_max=100 * _LAKH),
        ]

        (demand,) = aggregate_demand(projects=[project], leads=leads, bookings=[])

        # Midpoints are 50L and 100L; both are present, so the median is 75L.
        assert demand.median_budget_paise == 75 * _LAKH

    def test_leads_without_budgets_are_excluded(self) -> None:
        project = FakeProject(uuid4(), "Palm Grove", "Kondapur")
        leads = [
            _lead(project.id, budget_min=80 * _LAKH, budget_max=80 * _LAKH),
            _lead(project.id),
        ]

        (demand,) = aggregate_demand(projects=[project], leads=leads, bookings=[])

        assert demand.median_budget_paise == 80 * _LAKH
        assert demand.top_price_band == "50L-1Cr"


class TestTopPriceBand:
    def test_mixed_lead_budgets_and_booking_considerations(self) -> None:
        project = FakeProject(uuid4(), "Palm Grove", "Kondapur")
        leads = [
            _lead(project.id, budget_min=150 * _LAKH, budget_max=150 * _LAKH),
            _lead(project.id, budget_min=120 * _LAKH, budget_max=120 * _LAKH),
            _lead(project.id, budget_min=60 * _LAKH, budget_max=60 * _LAKH),
        ]
        bookings = [FakeBooking(project.id, consideration_paise=130 * _LAKH)]

        (demand,) = aggregate_demand(projects=[project], leads=leads, bookings=bookings)

        # Three "1-2Cr" values versus one "50L-1Cr".
        assert demand.top_price_band == "1-2Cr"

    def test_tie_is_broken_by_band_order(self) -> None:
        project = FakeProject(uuid4(), "Palm Grove", "Kondapur")
        leads = [
            _lead(project.id, budget_min=30 * _LAKH, budget_max=30 * _LAKH),
            _lead(project.id, budget_min=150 * _LAKH, budget_max=150 * _LAKH),
        ]

        (demand,) = aggregate_demand(projects=[project], leads=leads, bookings=[])

        # "<50L" precedes "1-2Cr" in DEFAULT_PRICE_BANDS.
        assert demand.top_price_band == "<50L"

    def test_bookings_alone_can_determine_band(self) -> None:
        project = FakeProject(uuid4(), "Palm Grove", "Kondapur")
        bookings = [FakeBooking(project.id, consideration_paise=250 * _LAKH)]

        (demand,) = aggregate_demand(projects=[project], leads=[], bookings=bookings)

        assert demand.top_price_band == ">2Cr"


class TestTopPropertyType:
    def test_groups_case_insensitively_and_keeps_most_common_casing(self) -> None:
        project = FakeProject(uuid4(), "Palm Grove", "Kondapur")
        leads = [
            _lead(project.id, config="3 BHK"),
            _lead(project.id, config="3 bhk"),
            _lead(project.id, config="2 BHK"),
        ]

        (demand,) = aggregate_demand(projects=[project], leads=leads, bookings=[])

        assert demand.top_property_type == "3 BHK"

    def test_excludes_none_and_empty_values(self) -> None:
        project = FakeProject(uuid4(), "Palm Grove", "Kondapur")
        leads = [
            _lead(project.id, config=None),
            _lead(project.id, config="   "),
            _lead(project.id, config="2 BHK"),
        ]

        (demand,) = aggregate_demand(projects=[project], leads=leads, bookings=[])

        assert demand.top_property_type == "2 BHK"

    def test_tie_is_broken_alphabetically(self) -> None:
        project = FakeProject(uuid4(), "Palm Grove", "Kondapur")
        leads = [
            _lead(project.id, config="4 BHK"),
            _lead(project.id, config="2 BHK"),
        ]

        (demand,) = aggregate_demand(projects=[project], leads=leads, bookings=[])

        assert demand.top_property_type == "2 BHK"


class TestOrdering:
    def test_sorted_by_lead_count_desc_then_locality_asc(self) -> None:
        first = FakeProject(uuid4(), "Alpha", "Whitefield")
        second = FakeProject(uuid4(), "Beta", "Anna Nagar")
        third = FakeProject(uuid4(), "Gamma", "Kondapur")
        leads = [
            _lead(second.id),
            _lead(second.id),
            _lead(third.id),
            _lead(first.id),
        ]

        demands = aggregate_demand(
            projects=[third, first, second], leads=leads, bookings=[]
        )

        assert [(d.locality, d.lead_count) for d in demands] == [
            ("Anna Nagar", 2),
            ("Kondapur", 1),
            ("Whitefield", 1),
        ]


class TestDefaults:
    def test_default_bands_cover_residential_range(self) -> None:
        labels = [band.label for band in DEFAULT_PRICE_BANDS]
        assert labels == ["<50L", "50L-1Cr", "1-2Cr", ">2Cr"]


@pytest.mark.parametrize(
    "paise,expected",
    [
        (0, "<50L"),
        (5_000_000, "<50L"),
        (5_000_001, "50L-1Cr"),
        (10_000_000, "50L-1Cr"),
        (10_000_001, "1-2Cr"),
        (20_000_000, "1-2Cr"),
        (20_000_001, ">2Cr"),
        (-5, UNKNOWN),
    ],
)
def test_price_band_boundary_matrix(paise: int, expected: str) -> None:
    assert price_band_for(paise) == expected
