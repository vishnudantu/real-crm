"""Connect dialer business logic: dispositions, DNC, callbacks, wallboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.connect_dialer.models import (
    CallbackStatus,
    CallDisposition,
    Disposition,
    DoNotCallEntry,
    ScheduledCallback,
    utcnow,
)
from app.modules.omnichannel.models import CallRecord, CallStatus
from app.modules.users.models import RoleName, User


def _require_staff(actor: User) -> None:
    if actor.role.name == RoleName.BUYER.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff role required.")


def is_suppressed(session: Session, *, tenant_id: UUID, phone_number: str) -> bool:
    """True if the number is on this tenant's Do-Not-Call list."""
    entry = session.scalar(
        select(DoNotCallEntry).where(
            DoNotCallEntry.tenant_id == tenant_id,
            DoNotCallEntry.phone_number == phone_number,
        )
    )
    return entry is not None


def assert_dialable(session: Session, *, tenant_id: UUID, phone_number: str) -> None:
    """Raise 409 if the destination is on the DNC list (call before dialing)."""
    if is_suppressed(session, tenant_id=tenant_id, phone_number=phone_number):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This number is on the Do-Not-Call list for this organization.",
        )


def record_disposition(
    session: Session, *, actor: User, call_id: UUID, disposition: Disposition, notes: str | None = None
) -> CallDisposition:
    """Record (or update) the outcome for a completed call. One per call."""
    _require_staff(actor)
    call = session.scalar(
        select(CallRecord).where(
            CallRecord.id == call_id, CallRecord.tenant_id == actor.tenant_id
        )
    )
    if call is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Call not found.")
    if call.status not in (
        CallStatus.COMPLETED.value, CallStatus.MISSED.value,
        CallStatus.FAILED.value, CallStatus.BUSY.value,
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "A disposition can only be recorded once the call has ended.",
        )
    existing = session.scalar(
        select(CallDisposition).where(
            CallDisposition.tenant_id == actor.tenant_id,
            CallDisposition.call_id == call_id,
        )
    )
    if existing is not None:
        existing.disposition = disposition.value
        existing.notes = notes
        existing.recorded_by_id = actor.id
        existing.updated_at = utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    row = CallDisposition(
        tenant_id=actor.tenant_id,
        call_id=call_id,
        disposition=disposition.value,
        notes=notes,
        recorded_by_id=actor.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def add_dnc_entry(session: Session, *, actor: User, phone_number: str, reason: str | None = None) -> DoNotCallEntry:
    """Add a number to the tenant DNC list (idempotent per number)."""
    _require_staff(actor)
    existing = session.scalar(
        select(DoNotCallEntry).where(
            DoNotCallEntry.tenant_id == actor.tenant_id,
            DoNotCallEntry.phone_number == phone_number,
        )
    )
    if existing is not None:
        return existing
    row = DoNotCallEntry(
        tenant_id=actor.tenant_id, phone_number=phone_number, reason=reason, added_by_id=actor.id
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_dnc(session: Session, *, tenant_id: UUID) -> list[DoNotCallEntry]:
    return list(
        session.scalars(
            select(DoNotCallEntry).where(DoNotCallEntry.tenant_id == tenant_id)
        ).all()
    )


def remove_dnc_entry(session: Session, *, actor: User, entry_id: UUID) -> None:
    _require_staff(actor)
    entry = session.scalar(
        select(DoNotCallEntry).where(
            DoNotCallEntry.id == entry_id, DoNotCallEntry.tenant_id == actor.tenant_id
        )
    )
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "DNC entry not found.")
    session.delete(entry)
    session.commit()


def schedule_callback(
    session: Session, *, actor: User, phone_number: str, scheduled_at: datetime,
    lead_id: UUID | None = None, call_id: UUID | None = None,
    assigned_to_id: UUID | None = None, notes: str | None = None,
) -> ScheduledCallback:
    """Schedule a callback; the assignee is reminded at scheduled_at."""
    _require_staff(actor)
    assert_dialable(session, tenant_id=actor.tenant_id, phone_number=phone_number)
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=UTC)
    row = ScheduledCallback(
        tenant_id=actor.tenant_id,
        lead_id=lead_id,
        call_id=call_id,
        phone_number=phone_number,
        assigned_to_id=assigned_to_id if assigned_to_id is not None else actor.id,
        scheduled_at=scheduled_at,
        status=CallbackStatus.SCHEDULED.value,
        notes=notes,
        created_by_id=actor.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_callbacks(
    session: Session, *, tenant_id: UUID, status_filter: str | None = None, only_overdue: bool = False
) -> list[ScheduledCallback]:
    conditions = [ScheduledCallback.tenant_id == tenant_id]
    if status_filter:
        conditions.append(ScheduledCallback.status == status_filter)
    if only_overdue:
        conditions.extend([
            ScheduledCallback.status == CallbackStatus.SCHEDULED.value,
            ScheduledCallback.scheduled_at < datetime.now(UTC),
        ])
    return list(
        session.scalars(
            select(ScheduledCallback).where(*conditions).order_by(ScheduledCallback.scheduled_at)
        ).all()
    )


def complete_callback(session: Session, *, actor: User, callback_id: UUID) -> ScheduledCallback:
    _require_staff(actor)
    row = session.scalar(
        select(ScheduledCallback).where(
            ScheduledCallback.id == callback_id,
            ScheduledCallback.tenant_id == actor.tenant_id,
        )
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Callback not found.")
    row.status = CallbackStatus.DONE.value
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def wallboard(session: Session, *, tenant_id: UUID) -> dict:
    """Live read-model for supervisors: call volume + agent availability."""
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    def count_calls(status_value: str) -> int:
        return int(
            session.scalar(
                select(func.count()).select_from(CallRecord).where(
                    CallRecord.tenant_id == tenant_id, CallRecord.status == status_value
                )
            ) or 0
        )

    completed_today = int(
        session.scalar(
            select(func.count()).select_from(CallRecord).where(
                CallRecord.tenant_id == tenant_id,
                CallRecord.status == CallStatus.COMPLETED.value,
                CallRecord.ended_at >= today_start,
            )
        ) or 0
    )
    waiting_callbacks = int(
        session.scalar(
            select(func.count()).select_from(ScheduledCallback).where(
                ScheduledCallback.tenant_id == tenant_id,
                ScheduledCallback.status == CallbackStatus.SCHEDULED.value,
            )
        ) or 0
    )
    overdue_callbacks = int(
        session.scalar(
            select(func.count()).select_from(ScheduledCallback).where(
                ScheduledCallback.tenant_id == tenant_id,
                ScheduledCallback.status == CallbackStatus.SCHEDULED.value,
                ScheduledCallback.scheduled_at < datetime.now(UTC),
            )
        ) or 0
    )
    # Agent availability is derived from active calls (an agent on a call is busy).
    busy_agents = int(
        session.scalar(
            select(func.count(func.distinct(CallRecord.agent_id))).where(
                CallRecord.tenant_id == tenant_id,
                CallRecord.status.in_(
                    (CallStatus.INITIATED.value, CallStatus.RINGING.value, CallStatus.IN_PROGRESS.value)
                ),
            )
        ) or 0
    )
    total_agents = int(
        session.scalar(
            select(func.count()).select_from(User).where(
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
                User.role_id.in_(
                    select(User.role_id).where(User.tenant_id == tenant_id)
                ),
            )
        ) or 0
    )
    # available = active staff not currently on a call; never negative.
    available = max(0, total_agents - busy_agents)
    return {
        "active_calls": count_calls(CallStatus.IN_PROGRESS.value),
        "ringing_calls": count_calls(CallStatus.RINGING.value) + count_calls(CallStatus.INITIATED.value),
        "waiting_callbacks": waiting_callbacks,
        "overdue_callbacks": overdue_callbacks,
        "completed_today": completed_today,
        "available_agents": available,
        "busy_agents": busy_agents,
    }
