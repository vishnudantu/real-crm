"""Broker registry business logic and commission performance aggregation."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.brokers.exceptions import BrokerNotFoundError
from app.modules.brokers.models import Broker
from app.modules.postsales.models import BrokerCommission, CommissionStatus


def get_broker(session: Session, broker_id: UUID, tenant_id: UUID) -> Broker:
    broker = session.scalar(
        select(Broker).where(Broker.id == broker_id, Broker.tenant_id == tenant_id)
    )
    if broker is None:
        raise BrokerNotFoundError()
    return broker


def register_broker(
    session: Session,
    *,
    actor,
    agency_name: str,
    contact_name: str,
    email: str | None = None,
    phone: str | None = None,
    rera_id: str | None = None,
    notes: str | None = None,
) -> Broker:
    """Create a broker; an existing agency+contact pair returns the original row."""

    existing = session.scalar(
        select(Broker).where(
            Broker.tenant_id == actor.tenant_id,
            Broker.agency_name == agency_name,
            Broker.contact_name == contact_name,
        )
    )
    if existing is not None:
        return existing

    broker = Broker(
        tenant_id=actor.tenant_id,
        agency_name=agency_name,
        contact_name=contact_name,
        email=email,
        phone=phone,
        rera_id=rera_id,
        notes=notes,
        created_by=actor.id,
    )
    session.add(broker)
    session.commit()
    session.refresh(broker)
    return broker


def update_broker(
    session: Session, *, actor, broker_id: UUID, fields: dict[str, Any]
) -> Broker:
    """Edit contact/status fields; agency identity needs a dedicated rename flow.

    All ACTIVE/INACTIVE/SUSPENDED transitions are permitted, so no additional
    transition matrix is needed beyond the request enum validation.
    """

    broker = get_broker(session, broker_id, tenant_id=actor.tenant_id)
    for field, value in fields.items():
        setattr(broker, field, value)
    session.add(broker)
    session.commit()
    session.refresh(broker)
    return broker


def list_brokers(
    session: Session,
    tenant_id: UUID,
    status: str | None = None,
    search: str | None = None,
) -> list[Broker]:
    conditions = [Broker.tenant_id == tenant_id]
    if status is not None:
        conditions.append(Broker.status == status)
    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append(Broker.agency_name.ilike(term) | Broker.contact_name.ilike(term))
    return list(
        session.scalars(
            select(Broker)
            .where(*conditions)
            .order_by(Broker.agency_name, Broker.contact_name, Broker.id)
        ).all()
    )


def broker_performance(session: Session, *, actor, broker_id: UUID) -> dict:
    """Roll up commissions where broker_name exactly matches the contact name."""

    broker = get_broker(session, broker_id, tenant_id=actor.tenant_id)
    by_status = {status.value: 0 for status in CommissionStatus}
    rows = session.execute(
        select(
            BrokerCommission.status,
            func.coalesce(func.sum(BrokerCommission.amount_paise), 0),
            func.count(BrokerCommission.id),
        ).where(
            BrokerCommission.tenant_id == actor.tenant_id,
            BrokerCommission.broker_name == broker.contact_name,
        ).group_by(BrokerCommission.status)
    ).all()
    total = 0
    deal_count = 0
    for commission_status, amount, count in rows:
        amount = int(amount or 0)
        by_status[commission_status] = amount
        total += amount
        deal_count += int(count)
    return {
        "broker_id": broker.id,
        "total_commission_paise": total,
        "by_status": by_status,
        "deal_count": deal_count,
    }
