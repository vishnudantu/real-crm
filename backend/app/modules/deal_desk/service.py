"""Deal-desk pricing policy services.

Responsibilities:

- Cost sheets: one project-generic sheet per project, one unit-specific sheet
  per unit. The four named components must be non-negative integer paise and
  the total is derived, never trusted from the client.
- Discount matrix: per tenant, editable, validated as an ascending ladder with
  exactly one open-ended blocked ceiling band. Defaults seed lazily so a
  tenant created after the migration still gets the policy.
- Quotes: validate a proposed discount against the matrix BEFORE anything is
  written. band1 (<=2%) needs one admin approval, band2 (<=5%) additionally
  requires a reason at request time, anything above the highest covered band
  is blocked at creation with a policy message.
- Discount requests: raise a quote into approvals as request_type
  "DEAL_DISCOUNT" (reference "deal_quote"). The existing decision dispatcher
  mirrors an APPROVED discount onto property_units.discount_status /
  approved_discount_paise via the new deal_quote handler, and the quote's net
  price is the exposed consideration. Money never changes in postsales: the
  approved discount reduces the consideration at booking creation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.approvals import service as approvals_service
from app.modules.approvals.exceptions import ApprovalAmountInvalidError
from app.modules.approvals.models import ApprovalRequest
from app.modules.deal_desk import repository
from app.modules.deal_desk.exceptions import (
    CostBreakdownInvalidError,
    CostSheetAlreadyExistsError,
    CostSheetNotFoundError,
    DealProjectNotFoundError,
    DealQuoteNotFoundError,
    DealUnitNotFoundError,
    DiscountBandBlockedError,
    DiscountMatrixInvalidError,
    DiscountReasonRequiredError,
    QuoteNotQuotableError,
)
from app.modules.deal_desk.models import (
    CostSheet,
    DiscountMatrixBand,
    DiscountQuote,
    QuoteStatus,
    default_matrix_rows,
)
from app.modules.deal_desk.schemas import MatrixUpdateRequest
from app.modules.inventory.exceptions import DiscountAlreadyRequestedError
from app.modules.inventory.models import DiscountStatus, PropertyUnit
from app.modules.projects.models import Project
from app.modules.users.models import User

DEAL_DISCOUNT_REQUEST_TYPE = "DEAL_DISCOUNT"
QUOTE_REFERENCE_TYPE = "deal_quote"
COST_SHEET_COMPONENT_KEYS = ("land", "construction", "amenities", "margin")
DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200


# ---------------------------------------------------------------------------
# Cost sheets
# ---------------------------------------------------------------------------


def _validated_components(components: dict[str, Any]) -> tuple[dict[str, int], int]:
    try:
        normalized = {key: int(components[key]) for key in COST_SHEET_COMPONENT_KEYS}
    except KeyError as error:
        raise CostBreakdownInvalidError(f"Missing cost component: {error.args[0]}.") from error
    except (TypeError, ValueError) as error:
        raise CostBreakdownInvalidError() from error
    if any(value < 0 for value in normalized.values()):
        raise CostBreakdownInvalidError("Cost components must be non-negative paise.")
    return normalized, sum(normalized.values())


def _require_project(session: Session, *, tenant_id: UUID, project_id: UUID) -> Project:
    project = session.query(Project).filter_by(
        id=project_id, tenant_id=tenant_id
    ).one_or_none()
    if project is None:
        raise DealProjectNotFoundError()
    return project


def _require_unit(session: Session, *, tenant_id: UUID, unit_id: UUID) -> PropertyUnit:
    unit = session.query(PropertyUnit).filter_by(
        id=unit_id, tenant_id=tenant_id
    ).one_or_none()
    if unit is None:
        raise DealUnitNotFoundError()
    return unit


def create_cost_sheet(
    session: Session,
    *,
    actor: User,
    project_id: UUID,
    components: dict[str, Any],
    unit_id: UUID | None = None,
    note: str | None = None,
) -> CostSheet:
    """Add the generic (project) or unit-specific sheet for one scope."""

    project = _require_project(session, tenant_id=actor.tenant_id, project_id=project_id)
    if unit_id is not None:
        unit = _require_unit(session, tenant_id=actor.tenant_id, unit_id=unit_id)
        if unit.project_id != project.id:
            raise DealUnitNotFoundError()
    if repository.find_cost_sheet(
        session, tenant_id=actor.tenant_id, project_id=project_id, unit_id=unit_id
    ) is not None:
        raise CostSheetAlreadyExistsError()
    normalized, total = _validated_components(components)
    sheet = CostSheet(
        tenant_id=actor.tenant_id,
        project_id=project_id,
        unit_id=unit_id,
        land_paise=normalized["land"],
        construction_paise=normalized["construction"],
        amenities_paise=normalized["amenities"],
        margin_paise=normalized["margin"],
        total_paise=total,
        cost_breakdown_json=normalized,
        note=note,
    )
    session.add(sheet)
    session.commit()
    session.refresh(sheet)
    return sheet


def get_cost_sheet(session: Session, *, actor: User, sheet_id: UUID) -> CostSheet:
    sheet = repository.get_cost_sheet(session, tenant_id=actor.tenant_id, sheet_id=sheet_id)
    if sheet is None:
        raise CostSheetNotFoundError()
    return sheet


def list_cost_sheets(
    session: Session, *, actor: User, project_id: UUID | None = None
) -> list[CostSheet]:
    return repository.list_cost_sheets(
        session, tenant_id=actor.tenant_id, project_id=project_id
    )


def update_cost_sheet(
    session: Session, *, actor: User, sheet_id: UUID, components: dict[str, Any],
    note: str | None = None,
) -> CostSheet:
    """Replace the breakdown (immutable scope: project/unit never move)."""

    sheet = get_cost_sheet(session, actor=actor, sheet_id=sheet_id)
    normalized, total = _validated_components(components)
    sheet.land_paise = normalized["land"]
    sheet.construction_paise = normalized["construction"]
    sheet.amenities_paise = normalized["amenities"]
    sheet.margin_paise = normalized["margin"]
    sheet.total_paise = total
    sheet.cost_breakdown_json = normalized
    if note is not None:
        sheet.note = note
    sheet.updated_at = datetime.now(UTC)
    session.add(sheet)
    session.commit()
    sheet = get_cost_sheet(session, actor=actor, sheet_id=sheet_id)
    return sheet


# ---------------------------------------------------------------------------
# Discount matrix
# ---------------------------------------------------------------------------


def get_or_create_matrix(session: Session, *, tenant_id: UUID) -> list[DiscountMatrixBand]:
    """The tenant's bands, seeded with the defaults on first touch."""

    bands = repository.bands_for_tenant(session, tenant_id=tenant_id)
    if bands:
        return bands
    now = datetime.now(UTC)
    bands = [
        DiscountMatrixBand(
            tenant_id=tenant_id,
            band_number=row["band_number"],
            max_discount_percent=row["max_discount_percent"],
            reason_required=row["reason_required"],
            blocked=row["blocked"],
            description=row["description"],
            created_at=now,
            updated_at=now,
        )
        for row in default_matrix_rows()
    ]
    session.add_all(bands)
    session.commit()
    return repository.bands_for_tenant(session, tenant_id=tenant_id)


def update_matrix(
    session: Session, *, actor: User, payload: MatrixUpdateRequest
) -> list[DiscountMatrixBand]:
    """Replace the tenant's band ladder after validation (band numbers 1..N)."""

    rows = payload.model_dump()
    for index, band in enumerate(rows["bands"]):
        if band["max_discount_percent"] is not None and index + 1 < len(rows["bands"]):
            # Ladder order was validated by the schema; re-check numerically
            # so a hand-built payload can never skip past the validator.
            next_band = rows["bands"][index + 1]
            if next_band["max_discount_percent"] is not None and (
                band["max_discount_percent"] >= next_band["max_discount_percent"]
            ):
                raise DiscountMatrixInvalidError("Band thresholds must ascend strictly.")
    now = datetime.now(UTC)
    for existing in repository.bands_for_tenant(session, tenant_id=actor.tenant_id):
        session.delete(existing)
    session.flush()
    bands = [
        DiscountMatrixBand(
            tenant_id=actor.tenant_id,
            band_number=index + 1,
            max_discount_percent=band["max_discount_percent"],
            reason_required=band["reason_required"],
            blocked=band["blocked"],
            description=band["description"],
            created_at=now,
            updated_at=now,
        )
        for index, band in enumerate(rows["bands"])
    ]
    session.add_all(bands)
    session.commit()
    return repository.bands_for_tenant(session, tenant_id=actor.tenant_id)


def resolve_band(bands: list[DiscountMatrixBand], percent: Decimal) -> DiscountMatrixBand:
    """The first band whose maximum covers percent; past all covered bands the
    open-ended band answers. A ladder without one is a policy error."""

    covered = [
        band for band in bands
        if band.max_discount_percent is not None and percent <= band.max_discount_percent
    ]
    if covered:
        return min(covered, key=lambda band: band.band_number)
    ceiling = [band for band in bands if band.max_discount_percent is None]
    if not ceiling:
        thresholds = [
            band.max_discount_percent for band in bands
            if band.max_discount_percent is not None
        ]
        raise DiscountMatrixInvalidError(
            "The discount matrix has no open-ended ceiling band; extend it above "
            f"{max(thresholds, default=Decimal('0'))}%."
        )
    return min(ceiling, key=lambda band: band.band_number)


def validate_discount_against_matrix(
    session: Session, *, tenant_id: UUID, percent: Decimal
) -> DiscountMatrixBand:
    """Band enforcement at creation. Blocked bands raise before any write.

    The reason rule (band 2 requires one) is applied by the caller that opens
    an approval request; quoting only checks the policy ceiling.
    """

    bands = get_or_create_matrix(session, tenant_id=tenant_id)
    band = resolve_band(bands, percent)
    if band.blocked:
        highest = max(
            (b.max_discount_percent for b in bands if b.max_discount_percent is not None),
            default=Decimal("0"),
        )
        raise DiscountBandBlockedError(percent, highest)
    return band


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


def _paise_for_percent(gross_paise: int, percent: Decimal) -> int:
    return int(
        (Decimal(gross_paise) * percent / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def create_quote(
    session: Session,
    *,
    actor: User,
    unit_id: UUID,
    gross_price_paise: int,
    discount_percent: Decimal,
    customer_ref: str | None = None,
) -> DiscountQuote:
    """Price a unit and validate the discount band immediately.

    A quote with a 0% discount is allowed (band 1, nothing to approve once
    raised); above the highest covered threshold it is rejected here with the
    policy message rather than at request time. The unit's cost sheets
    (unit-specific when present, else the project generic) are recorded on
    the snapshot via the unit-specific sheet id when one exists.
    """

    unit = _require_unit(session, tenant_id=actor.tenant_id, unit_id=unit_id)
    if gross_price_paise <= 0:
        raise CostBreakdownInvalidError("A quote needs a positive gross price.")
    if discount_percent < 0 or discount_percent > 100:
        raise CostBreakdownInvalidError("Discount percent must be within 0..100.")
    band = validate_discount_against_matrix(
        session, tenant_id=actor.tenant_id, percent=discount_percent
    )
    discount_paise = _paise_for_percent(gross_price_paise, discount_percent)
    if discount_paise > gross_price_paise:
        raise ApprovalAmountInvalidError()
    net_paise = gross_price_paise - discount_paise
    if net_paise <= 0:
        raise ApprovalAmountInvalidError()
    unit_sheet = repository.find_cost_sheet(
        session, tenant_id=actor.tenant_id, project_id=unit.project_id, unit_id=unit.id
    )
    quote = DiscountQuote(
        tenant_id=actor.tenant_id,
        unit_id=unit.id,
        project_id=unit.project_id,
        cost_sheet_id=unit_sheet.id if unit_sheet else None,
        gross_price_paise=gross_price_paise,
        discount_paise=discount_paise,
        discount_percent=discount_percent,
        net_price_paise=net_paise,
        band_number=band.band_number,
        status=QuoteStatus.QUOTED.value,
        customer_ref=customer_ref,
    )
    session.add(quote)
    session.commit()
    session.refresh(quote)
    return quote


def get_quote(session: Session, *, actor: User, quote_id: UUID) -> DiscountQuote:
    quote = repository.get_quote(session, tenant_id=actor.tenant_id, quote_id=quote_id)
    if quote is None:
        raise DealQuoteNotFoundError()
    return quote


def list_quotes(
    session: Session, *, actor: User, unit_id: UUID | None = None,
    limit: int = DEFAULT_LIST_LIMIT, offset: int = 0,
) -> list[DiscountQuote]:
    return repository.list_quotes(
        session,
        tenant_id=actor.tenant_id,
        unit_id=unit_id,
        limit=min(max(limit, 1), MAX_LIST_LIMIT),
        offset=max(offset, 0),
    )


def request_discount_from_quote(
    session: Session, *, actor: User, quote_id: UUID, reason: str | None = None
) -> tuple[DiscountQuote, ApprovalRequest]:
    """Open a DEAL_DISCOUNT approval for the quote's discount, atomically.

    Re-validates the band at request time (a matrix edit between quote and
    request can block or newly require a reason). Band 2 requires a non-empty
    reason; band 1 may pass without one. The unit is flagged PENDING on the
    same transaction so the approvals decision side-effect has an entity to
    mirror; APPROVE later writes approved_discount_paise through the existing
    dispatch path. 0%-discount quotes have nothing to approve and raise.
    """

    quote = get_quote(session, actor=actor, quote_id=quote_id)
    if quote.status == QuoteStatus.REQUESTED.value:
        raise QuoteNotQuotableError()
    if quote.discount_paise <= 0:
        raise ApprovalAmountInvalidError()
    band = validate_discount_against_matrix(
        session, tenant_id=actor.tenant_id, percent=quote.discount_percent
    )
    if band.reason_required and not (reason or "").strip():
        raise DiscountReasonRequiredError(band.band_number)
    unit = _require_unit(session, tenant_id=actor.tenant_id, unit_id=quote.unit_id)
    if unit.discount_status != DiscountStatus.NONE.value:
        # Another discount flow owns this unit's approval flag; do not steal it.
        raise DiscountAlreadyRequestedError()

    request = approvals_service.request_approval(
        session,
        actor=actor,
        request_type=DEAL_DISCOUNT_REQUEST_TYPE,
        reference_type=QUOTE_REFERENCE_TYPE,
        reference_id=quote.id,
        reason=(reason or "").strip() or f"Deal-desk quote {quote.id} at {quote.discount_percent}%.",
        amount_paise=quote.discount_paise,
        commit=False,
    )
    # Stamp the band onto the audit row so the approval alone is self-
    # describing: amount and matrix band, without joining back to the quote.
    request.reason = f"{request.reason} (band {band.band_number})"

    unit.discount_status = DiscountStatus.PENDING.value
    unit.updated_at = datetime.now(UTC)
    session.add(unit)

    quote.status = QuoteStatus.REQUESTED.value
    quote.band_number = band.band_number
    quote.updated_at = datetime.now(UTC)
    session.add(quote)

    # ONE commit publishes request + unit flag + quote state together.
    session.commit()
    session.refresh(request)
    session.refresh(quote)
    return quote, request
