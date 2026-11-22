"""Post-sales API: sale bookings, payment plans, receipts, demand letters, brokers."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser, CurrentUser, require_roles
from app.modules.users.models import RoleName, User
from app.modules.postsales import repository, service
from app.modules.postsales.schemas import (
    BrokerCommissionCreateRequest,
    BrokerCommissionResponse,
    BrokerCommissionUpdateRequest,
    InstallmentUpdateRequest,
    InstallmentWithPaid,
    PaymentPlanCreateRequest,
    PaymentPlanResponse,
    ReceiptCreateRequest,
    ReceiptResponse,
    ReceiptVoidRequest,
    SaleBookingCreateRequest,
    SaleBookingListResponse,
    SaleBookingResponse,
    SaleBookingUpdateRequest,
    SaleLedgerResponse,
)

router = APIRouter(prefix="/sales-bookings", tags=["post-sales"])


@router.post("", response_model=SaleBookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking_endpoint(
    payload: SaleBookingCreateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.create_booking(db, actor=admin, payload=payload)


@router.get("", response_model=SaleBookingListResponse)
def list_bookings_endpoint(
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    booking_status: Annotated[str | None, Query(alias="status")] = None,
    project_id: UUID | None = None,
    search: str | None = None,
):
    from app.modules.postsales import repository

    rows, total = repository.list_bookings(
        db,
        tenant_id=admin.tenant_id,
        offset=(page - 1) * page_size,
        limit=page_size,
        status=booking_status,
        project_id=project_id,
        search=search,
    )
    pages = (total + page_size - 1) // page_size if total else 0
    return SaleBookingListResponse(items=rows, total=total, page=page, page_size=page_size, pages=pages)


@router.get("/{booking_id}", response_model=SaleBookingResponse)
def get_booking_endpoint(
    booking_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    from app.modules.postsales import repository
    from app.modules.postsales.exceptions import SaleBookingNotFoundError

    booking = repository.get_booking(db, booking_id, tenant_id=current_user.tenant_id)
    if booking is None:
        raise SaleBookingNotFoundError()
    return booking


@router.patch("/{booking_id}", response_model=SaleBookingResponse)
def update_booking_endpoint(
    booking_id: UUID,
    payload: SaleBookingUpdateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.update_booking(db, actor=admin, booking_id=booking_id, payload=payload)


@router.get("/{booking_id}/ledger", response_model=SaleLedgerResponse)
def ledger_endpoint(
    booking_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.ledger(db, actor=current_user, booking_id=booking_id)


@router.post("/{booking_id}/plans", response_model=PaymentPlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan_endpoint(
    booking_id: UUID,
    payload: PaymentPlanCreateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.create_plan(db, actor=admin, booking_id=booking_id, payload=payload)


@router.post("/receipts", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED)
def record_receipt_endpoint(
    payload: ReceiptCreateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.record_receipt(db, actor=admin, payload=payload)


@router.get("/receipts/{receipt_id}", response_model=ReceiptResponse)
def get_receipt_endpoint(
    receipt_id: UUID,
    sales_user: Annotated[User, Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE))],
    db: Annotated[Session, Depends(get_db)],
):
    from app.modules.postsales.exceptions import ReceiptNotFoundError

    receipt = repository.get_receipt(db, receipt_id, tenant_id=sales_user.tenant_id)
    if receipt is None:
        raise ReceiptNotFoundError()
    return receipt


@router.post("/receipts/{receipt_id}/void", response_model=ReceiptResponse)
def void_receipt_endpoint(
    receipt_id: UUID,
    payload: ReceiptVoidRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    """Reverse a receipt's financial effect; the original row stays for audit."""

    return service.void_receipt(db, actor=admin, receipt_id=receipt_id, payload=payload)


@router.patch("/installments/{installment_id}", response_model=InstallmentWithPaid)
def update_installment_endpoint(
    installment_id: UUID,
    payload: InstallmentUpdateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    installment = service.update_installment(
        db, actor=admin, installment_id=installment_id, payload=payload
    )
    paid = repository.receipt_total_for_installment(
        db, installment.id, tenant_id=admin.tenant_id
    )
    result = InstallmentWithPaid(
        id=installment.id,
        plan_id=installment.plan_id,
        sequence_no=installment.sequence_no,
        milestone=installment.milestone,
        amount_paise=installment.amount_paise,
        due_on=installment.due_on,
        status=installment.status,
        demand_letter_sent_at=installment.demand_letter_sent_at,
        paid_paise=paid,
        outstanding_paise=max(0, installment.amount_paise - paid),
    )
    return result


@router.post(
    "/installments/{installment_id}/demand-letter",
    status_code=status.HTTP_204_NO_CONTENT,
)
def send_demand_letter_endpoint(
    installment_id: UUID,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    service.send_demand_letter(db, actor=admin, installment_id=installment_id)


@router.post("/{booking_id}/commissions", response_model=BrokerCommissionResponse, status_code=status.HTTP_201_CREATED)
def create_commission_endpoint(
    booking_id: UUID,
    payload: BrokerCommissionCreateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.create_commission(db, actor=admin, booking_id=booking_id, payload=payload)


@router.patch("/commissions/{commission_id}", response_model=BrokerCommissionResponse)
def update_commission_endpoint(
    commission_id: UUID,
    payload: BrokerCommissionUpdateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.update_commission(
        db, actor=admin, commission_id=commission_id, status_value=payload.status
    )
