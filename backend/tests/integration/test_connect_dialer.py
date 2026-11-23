"""Connect dialer: dispositions, DNC, callbacks, wallboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.connect_dialer import service
from app.modules.connect_dialer.models import (
    CallbackStatus,
    Disposition,
    DoNotCallEntry,
    ScheduledCallback,
)
from app.modules.omnichannel.models import CallDirection, CallRecord, CallStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD


def _tenant_admin(session: Session) -> tuple[Tenant, User]:
    tenant = Tenant(slug=f"dial-{uuid4().hex[:8]}", name="Dialer Co")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id, full_name="Agent One", email=f"agent.{tenant.id.hex[:8]}@dial.example",
        password_hash=hash_password(TEST_PASSWORD), role_id=role.id, is_active=True,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return tenant, admin


def _call(session: Session, admin: User, *, status=CallStatus.COMPLETED) -> CallRecord:
    call = CallRecord(
        tenant_id=admin.tenant_id, agent_id=admin.id,
        direction=CallDirection.OUTBOUND.value, status=status.value,
        provider="livekit", room_name=f"room-{uuid4().hex[:8]}",
        destination="+919800000000",
        ended_at=datetime.now(UTC) if status == CallStatus.COMPLETED else None,
    )
    session.add(call)
    session.commit()
    return call


def test_record_disposition_once_per_call(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _t, admin = _tenant_admin(session)
        call = _call(session, admin)
        row = service.record_disposition(
            session, actor=admin, call_id=call.id, disposition=Disposition.INTERESTED, notes="hot lead"
        )
        assert row.disposition == Disposition.INTERESTED.value
        # Re-recording updates rather than duplicating.
        again = service.record_disposition(
            session, actor=admin, call_id=call.id, disposition=Disposition.VISIT_CONFIRMED
        )
        assert again.id == row.id
        assert again.disposition == Disposition.VISIT_CONFIRMED.value


def test_disposition_requires_ended_call(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _t, admin = _tenant_admin(session)
        call = _call(session, admin, status=CallStatus.IN_PROGRESS)
        with pytest.raises(HTTPException) as exc:
            service.record_disposition(
                session, actor=admin, call_id=call.id, disposition=Disposition.INTERESTED
            )
        assert exc.value.status_code == 400


def test_dnc_blocks_dialing_and_callbacks(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _t, admin = _tenant_admin(session)
        service.add_dnc_entry(session, actor=admin, phone_number="+919800000000", reason="customer asked")
        assert service.is_suppressed(session, tenant_id=admin.tenant_id, phone_number="+919800000000")
        with pytest.raises(HTTPException) as exc:
            service.assert_dialable(session, tenant_id=admin.tenant_id, phone_number="+919800000000")
        assert exc.value.status_code == 409
        # Scheduling a callback to a DNC number is also blocked.
        with pytest.raises(HTTPException):
            service.schedule_callback(
                session, actor=admin, phone_number="+919800000000",
                scheduled_at=datetime.now(UTC) + timedelta(days=1),
            )


def test_dnc_add_is_idempotent_and_removable(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _t, admin = _tenant_admin(session)
        first = service.add_dnc_entry(session, actor=admin, phone_number="+919800000001")
        again = service.add_dnc_entry(session, actor=admin, phone_number="+919800000001")
        assert first.id == again.id
        service.remove_dnc_entry(session, actor=admin, entry_id=first.id)
        assert not service.is_suppressed(session, tenant_id=admin.tenant_id, phone_number="+919800000001")


def test_callback_lifecycle_and_overdue(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _t, admin = _tenant_admin(session)
        past = service.schedule_callback(
            session, actor=admin, phone_number="+919800000002",
            scheduled_at=datetime.now(UTC) - timedelta(hours=2),
        )
        future = service.schedule_callback(
            session, actor=admin, phone_number="+919800000003",
            scheduled_at=datetime.now(UTC) + timedelta(days=1),
        )
        overdue = service.list_callbacks(session, tenant_id=admin.tenant_id, only_overdue=True)
        assert len(overdue) == 1 and overdue[0].id == past.id

        done = service.complete_callback(session, actor=admin, callback_id=past.id)
        assert done.status == CallbackStatus.DONE.value
        # After completion, the overdue queue is empty.
        assert service.list_callbacks(session, tenant_id=admin.tenant_id, only_overdue=True) == []


def test_wallboard_counts(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _t, admin = _tenant_admin(session)
        _call(session, admin, status=CallStatus.IN_PROGRESS)
        _call(session, admin, status=CallStatus.COMPLETED)
        service.schedule_callback(
            session, actor=admin, phone_number="+919800000004",
            scheduled_at=datetime.now(UTC) - timedelta(hours=1),
        )
        board = service.wallboard(session, tenant_id=admin.tenant_id)
        assert board["active_calls"] == 1
        assert board["completed_today"] == 1
        assert board["overdue_callbacks"] == 1
        assert board["busy_agents"] >= 1


def test_cross_tenant_disposition_404(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _t, admin = _tenant_admin(session)
        call = _call(session, admin)
        # A different tenant's admin cannot record a disposition on this call.
        other_tenant = Tenant(slug=f"other-{uuid4().hex[:6]}", name="Other")
        session.add(other_tenant)
        session.flush()
        role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one()
        other_admin = User(
            tenant_id=other_tenant.id, full_name="Other Admin", email=f"o.{uuid4().hex[:6]}@x.example",
            password_hash=hash_password(TEST_PASSWORD), role_id=role.id, is_active=True,
        )
        session.add(other_admin)
        session.commit()
        session.refresh(other_admin)
        with pytest.raises(HTTPException) as exc:
            service.record_disposition(
                session, actor=other_admin, call_id=call.id, disposition=Disposition.INTERESTED
            )
        assert exc.value.status_code == 404
