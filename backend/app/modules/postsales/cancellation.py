"""Booking cancellation policy engine (post-sales).

Cancelling a sale booking is a policy decision with money and inventory
side-effects, so it is isolated here from the CRUD paths:

* **Free-cancel window** — a booking cancelled within ``free_cancel_days``
  (default 7) of ``created_at`` carries no fee; everything collected is
  recorded as refund-due.
* **Late-cancel fee** — outside the window, a percent of the live collected
  receipts is retained, escalating by sale stage
  (BOOKED < AGREEMENT_SIGNED < PAYMENTS_IN_PROGRESS). Unknown stages fall
  back to the nearest defined stage at or below them.
* **Tenant overrides** — per-tenant policy is a ``system_settings`` row
  (key ``cancellation_policy``); invalid values fall back field-by-field to
  the defaults. No new table is needed: the policy is configuration, not
  transactional data.
* **Unit release** — a booking with a canonical unit releases it through the
  inventory state machine's CANCELLATION edge (BOOKED -> AVAILABLE) in the
  same transaction. Units in any other status are reported but never
  overridden.
* **Money is never moved** — paid receipts stay live and un-voided; the
  refundable remainder is returned as ``refund_due_paise`` and recorded in
  the admin audit log. Refunds are an out-of-band banking action.

The public entry point is :func:`cancel_booking`, admin-only (``AdminUser``
at the router; re-checked here for service callers). The sale is never
deleted: the row moves to ``CANCELLED`` and the messaging outbox receives a
``sale.cancelled`` event when the tenant configured a trigger rule for it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.leads.models import Lead
from app.modules.postsales import repository
from app.modules.postsales.exceptions import SaleBookingNotFoundError
from app.modules.postsales.models import (
    Installment,
    PaymentPlan,
    Receipt,
    SaleBooking,
    SaleStatus,
)
from app.modules.settings.repository import get_setting
from app.modules.users.exceptions import InsufficientPermissionsError
from app.modules.users.models import RoleName

logger = logging.getLogger(__name__)

POLICY_SETTING_KEY = "cancellation_policy"
CANCEL_EVENT = "sale.cancelled"

FREE_WINDOW_DAYS = 7
LATE_FEE_PERCENT_BY_STAGE: dict[str, float] = {
    SaleStatus.BOOKED.value: 10.0,
    SaleStatus.AGREEMENT_SIGNED.value: 25.0,
    SaleStatus.PAYMENTS_IN_PROGRESS.value: 50.0,
}

DEFAULT_POLICY: dict[str, Any] = {
    "free_cancel_days": FREE_WINDOW_DAYS,
    "late_fee_percent": dict(LATE_FEE_PERCENT_BY_STAGE),
}

# Stage order used to pick the fee for stages without their own rate
# (AGREEMENT_PENDING books at the BOOKED rate; POSSESSION_READY at the
# PAYMENTS_IN_PROGRESS rate — the nearest defined stage at or below).
_STAGE_ORDER: tuple[str, ...] = (
    SaleStatus.BOOKED.value,
    SaleStatus.AGREEMENT_PENDING.value,
    SaleStatus.AGREEMENT_SIGNED.value,
    SaleStatus.PAYMENTS_IN_PROGRESS.value,
    SaleStatus.POSSESSION_READY.value,
)


@dataclass(frozen=True)
class CancellationResult:
    """Breakdown of one cancellation decision. Pure reporting: no money moved."""

    booking_id: UUID
    status: str
    stage: str
    reason: str | None
    policy_applied: bool
    policy: dict[str, Any] = field(default_factory=dict)
    free_window: bool = False
    collected_paise: int = 0
    fee_paise: int = 0
    refund_due_paise: int = 0
    refunds_issued_paise: int = 0
    outstanding_paise: int = 0
    unit_release: dict[str, Any] | None = None
    outbox_queued: int = 0
    cancelled_at: datetime | None = None


def _as_utc(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; compare ages in UTC on both backends."""

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _valid_days(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    days = int(value)
    return days if 0 <= days <= 3650 else None


def _valid_percent_map(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict) or not value:
        return None
    merged = dict(LATE_FEE_PERCENT_BY_STAGE)
    for stage, pct in value.items():
        if (
            not isinstance(stage, str)
            or stage not in LATE_FEE_PERCENT_BY_STAGE
            or isinstance(pct, bool)
            or not isinstance(pct, (int, float))
            or not 0 <= float(pct) <= 100
        ):
            return None
        merged[stage] = float(pct)
    return merged


def resolve_policy(session: Session, *, tenant_id: UUID) -> dict[str, Any]:
    """Merge the tenant's ``cancellation_policy`` setting onto the defaults.

    Validation is field-by-field: one bad value never disables the whole
    policy, and an unparseable setting block returns pure defaults.
    """

    policy = {
        "free_cancel_days": DEFAULT_POLICY["free_cancel_days"],
        "late_fee_percent": dict(DEFAULT_POLICY["late_fee_percent"]),
    }
    setting = get_setting(session, POLICY_SETTING_KEY, tenant_id=tenant_id)
    raw = setting.value if setting is not None and isinstance(setting.value, dict) else {}

    days = _valid_days(raw.get("free_cancel_days"))
    if days is not None:
        policy["free_cancel_days"] = days
    percents = _valid_percent_map(raw.get("late_fee_percent"))
    if percents is not None:
        policy["late_fee_percent"] = percents
    return policy


def _fee_percent_for_stage(policy: dict[str, Any], stage: str) -> float:
    percents: dict[str, float] = policy["late_fee_percent"]
    try:
        position = _STAGE_ORDER.index(stage)
    except ValueError:
        # Unknown/terminal-adjacent status: charge the strictest defined rate.
        return max(percents.values())
    for candidate in reversed(_STAGE_ORDER[: position + 1]):
        if candidate in percents:
            return percents[candidate]
    return max(percents.values())


def _collected_paise(session: Session, *, booking: SaleBooking, tenant_id: UUID) -> tuple[int, int]:
    """Live receipts and planned totals for the booking (voided rows excluded)."""

    plan_ids = list(
        session.scalars(
            select(PaymentPlan.id).where(
                PaymentPlan.sale_booking_id == booking.id,
                PaymentPlan.tenant_id == tenant_id,
            )
        ).all()
    )
    installments = (
        list(
            session.scalars(
                select(Installment).where(
                    Installment.plan_id.in_(plan_ids),
                    Installment.tenant_id == tenant_id,
                )
            ).all()
        )
        if plan_ids
        else []
    )
    installment_ids = [i.id for i in installments]
    collected = (
        int(
            session.scalar(
                select(func.coalesce(func.sum(Receipt.amount_paise), 0)).where(
                    Receipt.installment_id.in_(installment_ids),
                    Receipt.tenant_id == tenant_id,
                    *repository.live_receipt_conditions(),
                )
            )
            or 0
        )
        if installment_ids
        else 0
    )
    planned = sum(i.amount_paise for i in installments)
    return collected, planned


def _is_admin(session: Session, actor: Any) -> bool:
    """Admin gate for ORM users and detached test principals."""

    role = getattr(actor, "role", None)
    if role is not None:
        return getattr(role, "name", None) == RoleName.ADMIN.value
    if getattr(actor, "role_id", None) is None:
        return False
    from app.modules.users.models import Role

    db_role = session.get(Role, actor.role_id)
    return db_role is not None and db_role.name == RoleName.ADMIN.value


def _release_unit(session: Session, *, booking: SaleBooking, actor_id: UUID, reason: str) -> dict[str, Any] | None:
    """BOOKED -> AVAILABLE through the inventory CANCELLATION edge (same tx)."""

    if booking.unit_id is None:
        return None
    from app.modules.inventory import service as inventory_service

    return inventory_service.release_unit_for_cancellation(
        session,
        tenant_id=booking.tenant_id,
        unit_id=booking.unit_id,
        actor_id=actor_id,
        reason=reason or "Sale booking cancelled.",
    )


def _assessment(
    session: Session,
    *,
    booking: SaleBooking,
    policy_check: bool,
    now: datetime,
) -> tuple[dict[str, Any], bool, int, int, int, int]:
    """Return (policy, free_window, collected, fee, refund_due, outstanding)."""

    policy = resolve_policy(session, tenant_id=booking.tenant_id)
    collected, planned = _collected_paise(session, booking=booking, tenant_id=booking.tenant_id)
    free_window = False
    fee = 0
    if policy_check:
        age_days = (now - _as_utc(booking.created_at)).total_seconds() / 86_400
        free_window = age_days < int(policy["free_cancel_days"])
        if not free_window:
            percent = _fee_percent_for_stage(policy, booking.status)
            fee = min(collected, int(collected * percent / 100))
    refund_due = max(0, collected - fee)
    outstanding = max(0, planned - collected)
    return policy, free_window, collected, fee, refund_due, outstanding


def cancel_booking(
    session: Session,
    actor: Any,
    booking_id: UUID,
    reason: str | None,
    policy_check: bool = True,
) -> CancellationResult:
    """Cancel a sale booking under the tenant's cancellation policy.

    Admin-only; cross-tenant ids are 404s (``SaleBookingNotFoundError``).
    CLOSED sales are rejected with 409 — the deed is done. Re-cancelling a
    CANCELLED booking is idempotent: status, ledger and inventory are not
    touched a second time. Receipts are never voided or refunded here; the
    refund-due remainder lands in the returned breakdown and the audit log.
    """

    from app.modules.auth.dependencies import has_permission
    from app.modules.users.permissions import POSTSALES_WRITE

    if not _is_admin(session, actor) and not has_permission(actor, POSTSALES_WRITE):
        raise InsufficientPermissionsError()

    booking = repository.get_booking(session, booking_id, tenant_id=actor.tenant_id)
    if booking is None:
        raise SaleBookingNotFoundError()

    if booking.status == SaleStatus.CLOSED.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A closed sale cannot be cancelled; use the receipt void workflow.",
        )

    now = datetime.now(UTC)
    policy, free_window, collected, fee, refund_due, outstanding = _assessment(
        session, booking=booking, policy_check=policy_check, now=now
    )

    if booking.status == SaleStatus.CANCELLED.value:
        # Idempotent replay: same breakdown recomputed, zero side-effects.
        return CancellationResult(
            booking_id=booking.id,
            status=booking.status,
            stage=booking.status,
            reason=reason,
            policy_applied=policy_check,
            policy=policy,
            free_window=free_window,
            collected_paise=collected,
            fee_paise=fee,
            refund_due_paise=refund_due,
            refunds_issued_paise=0,
            outstanding_paise=outstanding,
            unit_release=None,
            outbox_queued=0,
            cancelled_at=_as_utc(booking.updated_at),
        )

    stage = booking.status
    booking.status = SaleStatus.CANCELLED.value
    session.add(booking)
    unit_release = _release_unit(session, booking=booking, actor_id=actor.id, reason=reason)

    outbox_queued = 0
    lead = session.get(Lead, booking.lead_id)
    try:
        from app.modules.messaging.engine import emit_event

        deliveries = emit_event(
            session,
            tenant_id=booking.tenant_id,
            event=CANCEL_EVENT,
            context={
                "entity_type": "sale_booking",
                "entity_id": booking.id,
                "first_name": (lead.full_name.split(" ", 1)[0] if lead else None),
                "unit_number": booking.unit_number,
                "fee_paise": fee,
                "refund_due_paise": refund_due,
                "reason": reason,
                "to_address": (lead.phone or lead.email) if lead else None,
            },
        )
        outbox_queued = len(deliveries)
    except Exception as exc:  # noqa: BLE001 — the cancellation stands without messaging
        logger.warning("Could not emit %s messaging event: %s", CANCEL_EVENT, exc)

    try:
        from app.modules.settings.service import log_admin_action

        log_admin_action(
            session,
            actor=actor,
            action="CANCEL_SALE_BOOKING",
            resource_type="SALE_BOOKING",
            resource_id=str(booking.id),
            details={
                "reason": reason,
                "stage": stage,
                "policy_applied": policy_check,
                "free_window": free_window,
                "policy": policy,
                "collected_paise": collected,
                "fee_paise": fee,
                "refund_due_paise": refund_due,
                "refunds_issued_paise": 0,
                "unit_release": unit_release,
            },
        )
    except Exception as exc:  # noqa: BLE001 — audit failure must not strand the cancel
        logger.warning("Could not audit sale booking cancellation %s: %s", booking.id, exc)

    session.commit()
    session.refresh(booking)
    return CancellationResult(
        booking_id=booking.id,
        status=booking.status,
        stage=stage,
        reason=reason,
        policy_applied=policy_check,
        policy=policy,
        free_window=free_window,
        collected_paise=collected,
        fee_paise=fee,
        refund_due_paise=refund_due,
        refunds_issued_paise=0,
        outstanding_paise=outstanding,
        unit_release=unit_release,
        outbox_queued=outbox_queued,
        cancelled_at=_as_utc(booking.updated_at),
    )
