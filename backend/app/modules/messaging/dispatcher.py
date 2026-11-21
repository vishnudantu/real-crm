"""Claim-based outbox dispatch with bounded retries and exponential backoff."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.messaging.models import DeliveryStatus, MessageDelivery
from app.modules.messaging.providers.factory import build_provider

CLAIM_TIMEOUT_MINUTES = 5
BASE_BACKOFF_SECONDS = 60


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def reclaim_stale_claims(session: Session, *, now: datetime) -> int:
    cutoff = now - timedelta(minutes=CLAIM_TIMEOUT_MINUTES)
    result = session.execute(
        update(MessageDelivery)
        .where(
            MessageDelivery.status == DeliveryStatus.SENDING.value,
            MessageDelivery.claimed_at < cutoff,
        )
        .values(status=DeliveryStatus.QUEUED.value, claimed_at=None)
    )
    return int(result.rowcount or 0)


def _claim(session: Session, delivery_id: UUID, *, now: datetime) -> bool:
    result = session.execute(
        update(MessageDelivery)
        .where(
            MessageDelivery.id == delivery_id,
            MessageDelivery.status == DeliveryStatus.QUEUED.value,
        )
        .values(
            status=DeliveryStatus.SENDING.value,
            claimed_at=now,
            attempts=MessageDelivery.attempts + 1,
            updated_at=now,
        )
    )
    return int(result.rowcount or 0) == 1


def _retry_at(now: datetime, attempts: int) -> datetime:
    return now + timedelta(seconds=BASE_BACKOFF_SECONDS * (2 ** max(0, attempts - 1)))


def process_due_deliveries(
    session: Session,
    *,
    now: datetime | None = None,
    batch_size: int = 50,
    provider_factory=None,
) -> dict[str, int]:
    """Deliver a bounded batch, tolerating duplicate worker claims.

    Compare-and-swap claiming prevents concurrent dispatchers from sending the
    same row. Provider errors become retryable queue entries or FAILED rows,
    never unhandled exceptions from the scheduler.
    """

    timestamp = _utc(now or datetime.now(UTC))
    settings = get_settings()
    reclaim_stale_claims(session, now=timestamp)
    ids = list(
        session.scalars(
            select(MessageDelivery.id)
            .where(
                MessageDelivery.status == DeliveryStatus.QUEUED.value,
                MessageDelivery.next_attempt_at <= timestamp,
            )
            .order_by(MessageDelivery.next_attempt_at)
            .limit(batch_size)
        ).all()
    )
    counts = {"sent": 0, "retrying": 0, "failed": 0}
    for delivery_id in ids:
        if not _claim(session, delivery_id, now=timestamp):
            continue
        delivery = session.get(MessageDelivery, delivery_id)
        try:
            factory = provider_factory or build_provider
            provider = factory(delivery.provider, settings)
            external_id = provider.send(
                to=delivery.to_address,
                body=delivery.body,
                context={
                    "channel": delivery.channel,
                    "event": delivery.event,
                    "tenant_id": str(delivery.tenant_id),
                },
            )
            delivery.status = DeliveryStatus.SENT.value
            delivery.provider_msg_id = external_id
            delivery.sent_at = timestamp
            delivery.error = None
            counts["sent"] += 1
        except Exception as exc:  # provider boundary must not kill the worker
            delivery.error = str(exc)[:4000]
            delivery.claimed_at = None
            if delivery.attempts < delivery.max_attempts:
                delivery.status = DeliveryStatus.QUEUED.value
                delivery.next_attempt_at = _retry_at(timestamp, delivery.attempts)
                counts["retrying"] += 1
            else:
                delivery.status = DeliveryStatus.FAILED.value
                counts["failed"] += 1
        delivery.updated_at = timestamp
        session.flush()
    session.commit()
    return counts
