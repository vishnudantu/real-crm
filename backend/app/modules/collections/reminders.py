"""Reminder sequencing: evaluate due dates daily and queue MessageDelivery rows.

Follows the existing messaging engine pattern (``messaging/engine.py``):
the job writes outbox rows in the caller's transaction and never dispatches
directly — the existing messaging dispatcher owns delivery, retries, and the
dispatch-time consent gate (``messaging/consent.py``). Reminders are queued
even for opted-out buyers; suppression is enforced at dispatch, which is the
auditable P0.4 behaviour.

Dedupe: a ``collection_reminders`` row keyed by (tenant, installment,
offset_key) plus the outbox idempotency key ``collection:{tenant}:{installment}:
{offset}`` together guarantee at-most-once queueing per offset.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.collections.models import CollectionReminder
from app.modules.collections.policy import resolve_policy
from app.modules.leads.models import Lead
from app.modules.messaging.models import DeliveryStatus, MessageChannel, MessageDelivery
from app.modules.messaging.providers.factory import provider_name
from app.modules.postsales import repository as postsales_repository
from app.modules.postsales.models import Installment, PaymentPlan, SaleBooking, SaleStatus
from app.modules.tenancy.models import Tenant

logger = logging.getLogger("propflow.collections.reminders")

COLLECTION_REMINDER_EVENT = "collection.reminder"


def offset_key(offset: int) -> str:
    """Canonical string form of an offset day for the dedupe unique key."""

    return str(int(offset))


def _recipient_for_booking(session: Session, *, booking: SaleBooking) -> Lead | None:
    lead = session.get(Lead, booking.lead_id)
    if lead is None or lead.tenant_id != booking.tenant_id:
        return None
    return lead


def _choose_channel(policy_channels: list[str], lead: Lead) -> tuple[str, str] | None:
    """Pick the first preferred channel the lead can actually receive.

    Preference order comes from policy; consent itself is NOT evaluated here
    because dispatch-time suppression (messaging/consent.py) is the single
    lawful-basis gate. We only require an address for the channel.
    """

    for channel in policy_channels:
        if channel == MessageChannel.EMAIL.value and lead.email:
            return channel, lead.email
        if channel in (MessageChannel.WHATSAPP.value, MessageChannel.SMS.value) and lead.phone:
            return channel, lead.phone
    # Fall back to any address so the dispatcher records an explicit
    # suppression reason rather than silently dropping the reminder.
    if lead.phone:
        return MessageChannel.SMS.value, lead.phone
    if lead.email:
        return MessageChannel.EMAIL.value, lead.email
    return None


def queue_due_reminders(
    session: Session,
    *,
    tenant_id: UUID,
    today: date | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Queue reminders whose (due_on + offset) is today and not yet queued.

    Does not commit: the caller owns the transaction, matching the outbox
    pattern. Returns counters for observability.
    """

    day = today or (now or datetime.now(UTC)).date()
    timestamp = now or datetime.now(UTC)
    policy = resolve_policy(session, tenant_id=tenant_id)
    offsets: list[int] = policy["offsets"]
    channels: list[str] = policy["channels"]
    counts = {"queued": 0, "skipped_existing": 0, "skipped_no_recipient": 0, "skipped_settled": 0}

    for offset in offsets:
        target_due = day - timedelta(days=offset)
        installments = list(
            session.scalars(
                select(Installment).where(
                    Installment.tenant_id == tenant_id,
                    Installment.due_on == target_due,
                    # Only OPEN installments should trigger a payment reminder;
                    # PAID/WAIVED are terminal and must never be chased.
                    Installment.status.in_(postsales_repository.OPEN_INSTALLMENT_STATUSES),
                )
            ).all()
        )
        if not installments:
            continue
        plan_ids = {i.plan_id for i in installments}
        plans = {
            plan.id: plan
            for plan in session.scalars(
                select(PaymentPlan).where(
                    PaymentPlan.id.in_(plan_ids),
                    PaymentPlan.tenant_id == tenant_id,
                    PaymentPlan.is_active.is_(True),
                )
            ).all()
        }
        booking_ids = {plan.sale_booking_id for plan in plans.values()}
        bookings = (
            {
                booking.id: booking
                for booking in session.scalars(
                    select(SaleBooking).where(
                        SaleBooking.id.in_(booking_ids),
                        SaleBooking.tenant_id == tenant_id,
                    )
                ).all()
            }
            if booking_ids
            else {}
        )
        existing = {
            row.installment_id
            for row in session.scalars(
                select(CollectionReminder).where(
                    CollectionReminder.tenant_id == tenant_id,
                    CollectionReminder.installment_id.in_([i.id for i in installments]),
                    CollectionReminder.offset_key == offset_key(offset),
                )
            ).all()
        }
        paid = postsales_repository.paid_map_for_plan(
            session, list(plan_ids), tenant_id=tenant_id,
        )
        for installment in installments:
            if installment.id in existing:
                counts["skipped_existing"] += 1
                continue
            plan = plans.get(installment.plan_id)
            booking = bookings.get(plan.sale_booking_id) if plan else None
            if plan is None or booking is None:
                continue
            if booking.status in (SaleStatus.CANCELLED.value, SaleStatus.CLOSED.value):
                counts["skipped_settled"] += 1
                continue
            live_paid = paid.get(installment.id, 0)
            if live_paid >= installment.amount_paise:
                counts["skipped_settled"] += 1
                continue
            lead = _recipient_for_booking(session, booking=booking)
            choice = _choose_channel(channels, lead) if lead else None
            if choice is None:
                counts["skipped_no_recipient"] += 1
                continue
            channel, address = choice
            outstanding = max(0, installment.amount_paise - live_paid)
            key = f"collection:{tenant_id}:{installment.id}:{offset_key(offset)}"
            # The daily job only fires on the offset day itself, so the row is
            # immediately due; deterministic next_attempt_at keeps the daily
            # cadence owned by this scheduler, not the dispatcher.
            scheduled = timestamp
            # Claim the dedupe slot FIRST inside a savepoint: a concurrent
            # worker that already queued this (installment, offset) rolls back
            # only our claim, and no outbox row is created for the loser.
            reminder = CollectionReminder(
                tenant_id=tenant_id,
                installment_id=installment.id,
                offset_key=offset_key(offset),
                channel=channel,
                scheduled_for=scheduled,
                queued_at=timestamp,
                created_at=timestamp,
            )
            session.add(reminder)
            savepoint = session.begin_nested()
            try:
                session.flush()
            except IntegrityError:
                savepoint.rollback()
                counts["skipped_existing"] += 1
                continue
            savepoint.commit()
            delivery = MessageDelivery(
                tenant_id=tenant_id,
                channel=channel,
                to_address=address,
                body=(
                    f"Payment reminder: {installment.milestone} for unit "
                    f"{booking.unit_number} is due on {installment.due_on.isoformat()}. "
                    f"Outstanding: INR {outstanding / 100:.2f}."
                ),
                provider=provider_name(channel, get_settings()),
                status=DeliveryStatus.QUEUED.value,
                event=COLLECTION_REMINDER_EVENT,
                entity_type="installment",
                entity_id=installment.id,
                idempotency_key=key,
                next_attempt_at=scheduled,
                created_at=timestamp,
                updated_at=timestamp,
            )
            session.add(delivery)
            session.flush()
            counts["queued"] += 1
    return counts


def queue_all_tenants(session: Session, *, today: date | None = None) -> dict[str, int]:
    """Run the daily evaluation for every tenant. One commit per tenant so a
    single tenant's failure cannot roll back the others' queued reminders."""

    totals = {"queued": 0, "skipped_existing": 0, "skipped_no_recipient": 0, "skipped_settled": 0}
    tenant_ids = list(session.scalars(select(Tenant.id)).all())
    for tenant_id in tenant_ids:
        try:
            counts = queue_due_reminders(session, tenant_id=tenant_id, today=today)
            session.commit()
            for name, value in counts.items():
                totals[name] += value
        except Exception:  # noqa: BLE001 — one tenant must not stop the fleet
            session.rollback()
            logger.exception("Collections reminder pass failed for tenant %s", tenant_id)
    return totals


def last_reminder_map(
    session: Session, *, tenant_id: UUID, installment_ids: list[UUID]
) -> dict[UUID, datetime]:
    """Most recent queued reminder timestamp per installment (for the calendar)."""

    if not installment_ids:
        return {}
    rows = session.execute(
        select(
            CollectionReminder.installment_id,
            func.max(CollectionReminder.queued_at),
        )
        .where(
            CollectionReminder.tenant_id == tenant_id,
            CollectionReminder.installment_id.in_(installment_ids),
        )
        .group_by(CollectionReminder.installment_id)
    ).all()
    return {row[0]: row[1] for row in rows}
