"""Customer 360 timeline aggregation across modules (PF-009).

Reads are tenant-scoped and resolve the contact graph via the
``Opportunity.lead_id`` back-reference (the ``leads`` table is never modified).
Money stays in ``postsales`` and messaging in ``conversations``/``omnichannel``;
this module only references ids.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.bookings.models import Booking
from app.modules.conversations.models import Conversation, Message
from app.modules.customers.exceptions import ContactNotFoundError
from app.modules.customers.models import Contact, Opportunity
from app.modules.customers.schemas import (
    ContactDetailResponse,
    Customer360Response,
    OpportunityResponse,
    TimelineItem,
)
from app.modules.leads.models import Lead
from app.modules.omnichannel.models import (
    CallRecord,
    ChannelConversation,
    ChannelMessage,
)
from app.modules.postsales.models import (
    Installment,
    PaymentPlan,
    Receipt,
    SaleBooking,
)

_TIMELINE_CAP = 200


def _freshness(timestamps: list[datetime | None]) -> datetime | None:
    values = [t for t in timestamps if t is not None]
    return max(values) if values else None


def build_customer_360(
    session: Session, *, tenant_id: UUID, contact_id: UUID
) -> Customer360Response:
    """Aggregate the contact graph + cross-module timeline (cap 200, desc)."""
    contact = session.scalar(
        select(Contact)
        .options(selectinload(Contact.methods))
        .where(Contact.id == contact_id, Contact.tenant_id == tenant_id)
    )
    if contact is None:
        raise ContactNotFoundError()

    opportunities = list(
        session.scalars(
            select(Opportunity).where(
                Opportunity.tenant_id == tenant_id,
                Opportunity.contact_id == contact_id,
            )
        ).all()
    )
    lead_ids = [o.lead_id for o in opportunities if o.lead_id is not None]

    items: list[TimelineItem] = []
    freshness: dict[str, datetime | None] = {}

    # Leads
    lead_ts: list[datetime | None] = []
    if lead_ids:
        leads = list(
            session.scalars(
                select(Lead).where(
                    Lead.tenant_id == tenant_id, Lead.id.in_(lead_ids)
                )
            ).all()
        )
        for lead in leads:
            items.append(
                TimelineItem(
                    type="lead",
                    occurred_at=lead.created_at,
                    actor=None,
                    summary=f"Lead captured ({lead.source}) — {lead.full_name}",
                    link_ids={"lead_id": str(lead.id)},
                )
            )
            lead_ts.append(lead.created_at)
    freshness["leads"] = _freshness(lead_ts)

    # Conversations + Messages
    conv_ts: list[datetime | None] = []
    if lead_ids:
        convs = list(
            session.scalars(
                select(Conversation).where(
                    Conversation.tenant_id == tenant_id,
                    Conversation.lead_id.in_(lead_ids),
                )
            ).all()
        )
        conv_ids = [c.id for c in convs]
        for conv in convs:
            items.append(
                TimelineItem(
                    type="conversation",
                    occurred_at=conv.created_at,
                    actor=None,
                    summary=f"Conversation opened ({conv.status})",
                    link_ids={"conversation_id": str(conv.id), "lead_id": str(conv.lead_id)},
                )
            )
            conv_ts.append(conv.created_at)
        if conv_ids:
            messages = list(
                session.scalars(
                    select(Message).where(
                        Message.tenant_id == tenant_id,
                        Message.conversation_id.in_(conv_ids),
                    )
                ).all()
            )
            for msg in messages:
                preview = (msg.content or "")[:120]
                items.append(
                    TimelineItem(
                        type="message",
                        occurred_at=msg.created_at,
                        actor=msg.sender_type,
                        summary=preview,
                        link_ids={
                            "message_id": str(msg.id),
                            "conversation_id": str(msg.conversation_id),
                        },
                    )
                )
                conv_ts.append(msg.created_at)
    freshness["conversations"] = _freshness(conv_ts)

    # Channel conversations + messages
    chan_ts: list[datetime | None] = []
    if lead_ids:
        chans = list(
            session.scalars(
                select(ChannelConversation).where(
                    ChannelConversation.tenant_id == tenant_id,
                    ChannelConversation.lead_id.in_(lead_ids),
                )
            ).all()
        )
        chan_ids = [c.id for c in chans]
        for ch in chans:
            items.append(
                TimelineItem(
                    type="channel_conversation",
                    occurred_at=ch.created_at,
                    actor=None,
                    summary=f"{ch.channel} thread ({ch.status})",
                    link_ids={"channel_conversation_id": str(ch.id)},
                )
            )
            chan_ts.append(ch.last_message_at or ch.created_at)
        if chan_ids:
            cmsgs = list(
                session.scalars(
                    select(ChannelMessage).where(
                        ChannelMessage.tenant_id == tenant_id,
                        ChannelMessage.conversation_id.in_(chan_ids),
                    )
                ).all()
            )
            for cm in cmsgs:
                items.append(
                    TimelineItem(
                        type="channel_message",
                        occurred_at=cm.created_at,
                        actor=cm.direction,
                        summary=(cm.content or "")[:120],
                        link_ids={
                            "channel_message_id": str(cm.id),
                            "channel_conversation_id": str(cm.conversation_id),
                        },
                    )
                )
                chan_ts.append(cm.created_at)
    freshness["channels"] = _freshness(chan_ts)

    # Bookings (site visits)
    booking_ts: list[datetime | None] = []
    if lead_ids:
        bookings = list(
            session.scalars(
                select(Booking).where(
                    Booking.tenant_id == tenant_id, Booking.lead_id.in_(lead_ids)
                )
            ).all()
        )
        for b in bookings:
            items.append(
                TimelineItem(
                    type="booking",
                    occurred_at=b.created_at,
                    actor=None,
                    summary=f"Site visit {b.status}",
                    link_ids={"booking_id": str(b.id), "lead_id": str(b.lead_id)},
                )
            )
            booking_ts.append(b.created_at)
    freshness["bookings"] = _freshness(booking_ts)

    # Calls
    call_ts: list[datetime | None] = []
    if lead_ids:
        calls = list(
            session.scalars(
                select(CallRecord).where(
                    CallRecord.tenant_id == tenant_id,
                    CallRecord.lead_id.in_(lead_ids),
                )
            ).all()
        )
        for call in calls:
            items.append(
                TimelineItem(
                    type="call",
                    occurred_at=call.created_at,
                    actor=call.direction,
                    summary=f"Call {call.status} ({call.duration_seconds}s)",
                    link_ids={"call_id": str(call.id)},
                )
            )
            call_ts.append(call.created_at)
    freshness["calls"] = _freshness(call_ts)

    # Sale bookings + receipts
    sale_ts: list[datetime | None] = []
    if lead_ids:
        sales = list(
            session.scalars(
                select(SaleBooking).where(
                    SaleBooking.tenant_id == tenant_id,
                    SaleBooking.lead_id.in_(lead_ids),
                )
            ).all()
        )
        sale_ids = [s.id for s in sales]
        for s in sales:
            items.append(
                TimelineItem(
                    type="sale_booking",
                    occurred_at=s.created_at,
                    actor=None,
                    summary=f"Sale booked — unit {s.unit_number} ({s.status})",
                    link_ids={"sale_booking_id": str(s.id), "lead_id": str(s.lead_id)},
                )
            )
            sale_ts.append(s.created_at)
        if sale_ids:
            receipts = list(
                session.scalars(
                    select(Receipt)
                    .join(Installment, Installment.id == Receipt.installment_id)
                    .join(PaymentPlan, PaymentPlan.id == Installment.plan_id)
                    .where(
                        Receipt.tenant_id == tenant_id,
                        PaymentPlan.sale_booking_id.in_(sale_ids),
                    )
                ).all()
            )
            for r in receipts:
                items.append(
                    TimelineItem(
                        type="receipt",
                        occurred_at=r.paid_at,
                        actor=None,
                        summary=f"Receipt {r.receipt_number} — {r.amount_paise} paise",
                        link_ids={"receipt_id": str(r.id)},
                    )
                )
                sale_ts.append(r.paid_at)
    freshness["sales"] = _freshness(sale_ts)

    items.sort(key=lambda i: i.occurred_at, reverse=True)
    items = items[:_TIMELINE_CAP]

    return Customer360Response(
        contact=ContactDetailResponse.model_validate(contact),
        opportunities=[OpportunityResponse.model_validate(o) for o in opportunities],
        timeline=items,
        freshness=freshness,
    )
