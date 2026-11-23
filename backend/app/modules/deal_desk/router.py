"""Deal desk API: cost sheets, discount matrix, quotes, discount requests.

Staff-gated through the permission registry (deal_desk.read / deal_desk.manage
/ approvals.decide pattern): reads need DEAL_DESK_READ; cost-sheet writes and
matrix edits need DEAL_DESK_MANAGE (admin/manager legacy gate); opening a
DEAL_DISCOUNT approval from a quote uses the same staff gate as approvals
requests (admin/sales via APPROVALS_REQUEST). Decisions stay on the approvals
router (admin-only), keeping the single decision path for every flow.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.deal_desk import service
from app.modules.deal_desk.schemas import (
    CostSheetCreateRequest,
    CostSheetListResponse,
    CostSheetResponse,
    CostSheetUpdateRequest,
    DealDiscountRequestResponse,
    DiscountRequestCreate,
    MatrixBandResponse,
    MatrixResponse,
    MatrixUpdateRequest,
    QuoteCreateRequest,
    QuoteListResponse,
    QuoteResponse,
)
from app.modules.users.models import User
from app.modules.users.permissions import (
    APPROVALS_REQUEST,
    DEAL_DESK_MANAGE,
    DEAL_DESK_READ,
)

router = APIRouter(prefix="/deal-desk", tags=["deal-desk"])

DealDeskReader = Annotated[User, Depends(require_permission(DEAL_DESK_READ))]
DealDeskManager = Annotated[User, Depends(require_permission(DEAL_DESK_MANAGE))]
DiscountRequester = Annotated[User, Depends(require_permission(APPROVALS_REQUEST))]
Database = Annotated[Session, Depends(get_db)]


# ---------------------------------------------------------------------------
# Cost sheets
# ---------------------------------------------------------------------------


@router.post(
    "/cost-sheets",
    response_model=CostSheetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cost_sheet(
    payload: CostSheetCreateRequest, actor: DealDeskManager, db: Database
) -> CostSheetResponse:
    """Add a project-generic (unit_id omitted) or unit-specific cost sheet."""

    sheet = service.create_cost_sheet(
        db,
        actor=actor,
        project_id=payload.project_id,
        components=payload.components.as_paise_dict(),
        unit_id=payload.unit_id,
        note=payload.note,
    )
    return CostSheetResponse.model_validate(sheet)


@router.get("/cost-sheets", response_model=CostSheetListResponse)
def list_cost_sheets(
    actor: DealDeskReader,
    db: Database,
    project_id: UUID | None = None,
) -> CostSheetListResponse:
    sheets = service.list_cost_sheets(db, actor=actor, project_id=project_id)
    return CostSheetListResponse(
        items=[CostSheetResponse.model_validate(sheet) for sheet in sheets],
        total=len(sheets),
    )


@router.get("/cost-sheets/{sheet_id}", response_model=CostSheetResponse)
def get_cost_sheet(sheet_id: UUID, actor: DealDeskReader, db: Database) -> CostSheetResponse:
    return CostSheetResponse.model_validate(service.get_cost_sheet(db, actor=actor, sheet_id=sheet_id))


@router.patch("/cost-sheets/{sheet_id}", response_model=CostSheetResponse)
def update_cost_sheet(
    sheet_id: UUID, payload: CostSheetUpdateRequest, actor: DealDeskManager, db: Database
) -> CostSheetResponse:
    sheet = service.update_cost_sheet(
        db, actor=actor, sheet_id=sheet_id,
        components=payload.components.as_paise_dict(), note=payload.note,
    )
    return CostSheetResponse.model_validate(sheet)


# ---------------------------------------------------------------------------
# Discount matrix
# ---------------------------------------------------------------------------


@router.get("/discount-matrix", response_model=MatrixResponse)
def get_discount_matrix(actor: DealDeskReader, db: Database) -> MatrixResponse:
    """The tenant's band ladder; defaults are seeded on first read."""

    bands = service.get_or_create_matrix(db, tenant_id=actor.tenant_id)
    return MatrixResponse(
        tenant_id=actor.tenant_id,
        bands=[MatrixBandResponse.model_validate(band) for band in bands],
    )


@router.put("/discount-matrix", response_model=MatrixResponse)
def put_discount_matrix(
    payload: MatrixUpdateRequest, actor: DealDeskManager, db: Database
) -> MatrixResponse:
    """Replace the whole ladder (ascending thresholds, one blocked ceiling)."""

    bands = service.update_matrix(db, actor=actor, payload=payload)
    return MatrixResponse(
        tenant_id=actor.tenant_id,
        bands=[MatrixBandResponse.model_validate(band) for band in bands],
    )


# ---------------------------------------------------------------------------
# Quotes and DEAL_DISCOUNT approvals
# ---------------------------------------------------------------------------


@router.post("/quotes", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
def create_quote(payload: QuoteCreateRequest, actor: DealDeskReader, db: Database) -> QuoteResponse:
    """Price a unit; the discount percent is validated against the matrix now."""

    quote = service.create_quote(
        db,
        actor=actor,
        unit_id=payload.unit_id,
        gross_price_paise=payload.gross_price_paise,
        discount_percent=payload.discount_percent,
        customer_ref=payload.customer_ref,
    )
    return QuoteResponse.model_validate(quote)


@router.get("/quotes", response_model=QuoteListResponse)
def list_quotes(
    actor: DealDeskReader,
    db: Database,
    unit_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=service.MAX_LIST_LIMIT)] = service.DEFAULT_LIST_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> QuoteListResponse:
    items = service.list_quotes(db, actor=actor, unit_id=unit_id, limit=limit, offset=offset)
    return QuoteListResponse(
        items=[QuoteResponse.model_validate(quote) for quote in items], total=len(items)
    )


@router.get("/quotes/{quote_id}", response_model=QuoteResponse)
def get_quote(quote_id: UUID, actor: DealDeskReader, db: Database) -> QuoteResponse:
    return QuoteResponse.model_validate(service.get_quote(db, actor=actor, quote_id=quote_id))


@router.post(
    "/quotes/{quote_id}/discount-request",
    response_model=DealDiscountRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_discount(
    quote_id: UUID, payload: DiscountRequestCreate, actor: DiscountRequester, db: Database
) -> DealDiscountRequestResponse:
    """Open a DEAL_DISCOUNT approval for the quote (band re-validated here)."""

    quote, request = service.request_discount_from_quote(
        db, actor=actor, quote_id=quote_id, reason=payload.reason
    )
    return DealDiscountRequestResponse(
        approval_request_id=request.id,
        quote_id=quote.id,
        unit_id=quote.unit_id,
        band_number=quote.band_number,
        discount_percent=quote.discount_percent,
        status=request.status,
        amount_paise=request.amount_paise,
        net_price_paise=quote.net_price_paise,
    )
