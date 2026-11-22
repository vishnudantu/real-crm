"""Dispatch-time consent enforcement for outbound customer messaging.

Blueprint P0.4: queueing a message is not consent. A lawful basis must still
hold at dispatch time — a lead can opt out, or the tenant can be suspended,
after the trigger fired. This module resolves the recipient of a queued
delivery and decides whether the provider may be called now.

Rules
- Recipients are resolved within the delivery's own tenant only.
- Internal staff sends (sales executives / admins receiving operational events
  such as lead assignment or handoff alerts) are governed by account and
  tenant activity, not marketing consent.
- Buyer sends are suppressed when the matched lead(s) are opted out (DPDP).
- Marketing-style events additionally require ``consent_to_contact``.
- Transactional events (booking confirmations, visit reminders) follow the
  contract-performance basis: suppressed only by explicit opt-out.
- An external address that resolves to no lead and no staff account is
  suppressed unless it belongs to a live booking of the same tenant.
- Suspended or missing tenants can never generate new external sends.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.bookings.models import Booking
from app.modules.leads.models import Lead, LeadAssignment
from app.modules.messaging.models import MessageDelivery
from app.modules.tenancy.models import Tenant, TenantStatus
from app.modules.users.models import RoleName, User

# Events that serve an existing request/contract rather than marketing.
TRANSACTIONAL_EVENTS = frozenset({
    "booking_confirmed",
    "booking_cancelled",
    "booking_rescheduled",
    "visit_reminder_24h",
    "visit_reminder_2h",
    "lead_assigned",
    "handoff_assigned",
    "handoff_status",
})


@dataclass(frozen=True)
class ConsentDecision:
    allowed: bool
    reason: str | None = None


def _phone_digits(value: str) -> str:
    return "".join(character for character in value or "" if character.isdigit())[-10:]


def _matches_user(user: User, address: str) -> bool:
    if user.email and user.email == address.strip().lower():
        return True
    digits = _phone_digits(address)
    return bool(digits) and digits == _phone_digits(user.phone or "")


def _matching_leads(session: Session, *, tenant_id: UUID, address: str) -> list[Lead]:
    if "@" in address:
        return list(
            session.scalars(
                select(Lead).where(Lead.tenant_id == tenant_id, Lead.email == address)
            ).all()
        )
    digits = _phone_digits(address)
    if not digits:
        return []
    rows = session.scalars(
        select(Lead).where(Lead.tenant_id == tenant_id, Lead.phone.is_not(None))
    ).all()
    return [lead for lead in rows if _phone_digits(lead.phone or "") == digits]


def _matching_staff(session: Session, *, tenant_id: UUID, address: str) -> User | None:
    """An active SALES_EXECUTIVE/ADMIN whose email or phone matches address.

    Notification ``to_address`` values are built directly from user records,
    so exact equality on indexed email/phone is sufficient and avoids a scan.
    """

    normalized_email = address.strip().lower()
    digits = _phone_digits(address)
    candidates = session.scalars(
        select(User).where(
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
            or_(
                User.email == normalized_email,
                *( [User.phone.is_not(None)] if digits else [] ),
            ),
        )
    ).all()
    for user in candidates:
        if user.role.name in (RoleName.SALES_EXECUTIVE.value, RoleName.ADMIN.value):
            if _matches_user(user, address):
                return user
    return None


def _staff_by_assignment(session: Session, *, delivery: MessageDelivery, address: str) -> bool:
    """True when the address is the currently assigned executive of the lead."""

    if delivery.entity_type != "lead" or delivery.entity_id is None:
        return False
    assignment = session.scalar(
        select(LeadAssignment).where(
            LeadAssignment.lead_id == delivery.entity_id,
            LeadAssignment.unassigned_at.is_(None),
        )
    )
    if assignment is None or assignment.executive_id is None:
        return False
    executive = session.get(User, assignment.executive_id)
    return bool(
        executive is not None
        and executive.is_active
        and executive.tenant_id == delivery.tenant_id
        and _matches_user(executive, address)
    )


def evaluate(session: Session, *, delivery: MessageDelivery) -> ConsentDecision:
    """Decide whether this queued delivery may contact its recipient now."""

    tenant = session.get(Tenant, delivery.tenant_id)
    if tenant is None or tenant.status != TenantStatus.ACTIVE.value:
        return ConsentDecision(False, "TENANT_INACTIVE")

    address = delivery.to_address.strip().lower()
    if not address:
        return ConsentDecision(False, "INVALID_RECIPIENT")

    # Internal operational sends target staff accounts: governed by account
    # activity, not buyer marketing consent.
    staff = _matching_staff(session, tenant_id=delivery.tenant_id, address=address)
    if staff is not None or _staff_by_assignment(session, delivery=delivery, address=address):
        return ConsentDecision(True)

    leads = _matching_leads(session, tenant_id=delivery.tenant_id, address=address)
    transactional = delivery.event in TRANSACTIONAL_EVENTS

    if not leads:
        if transactional and delivery.entity_type == "booking" and delivery.entity_id is not None:
            booking = session.get(Booking, delivery.entity_id)
            if booking is not None and booking.tenant_id == delivery.tenant_id:
                return ConsentDecision(True)
        return ConsentDecision(False, "NO_LAWFUL_BASIS_FOUND")

    if any(lead.opted_out for lead in leads):
        return ConsentDecision(False, "RECIPIENT_OPTED_OUT")

    if not transactional and not any(lead.consent_to_contact for lead in leads):
        return ConsentDecision(False, "MARKETING_CONSENT_ABSENT")

    return ConsentDecision(True)
