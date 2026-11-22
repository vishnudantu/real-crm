"""PF-010 evidence: canonical units, availability state machine, atomic holds.

Blueprint acceptance criteria (feature.md §50 rows 1-2/11/12 + 21.4):
- 20 concurrent acquire_hold on one unit from distinct sessions -> exactly one
  success, rest 409, final status ON_HOLD, one ACTIVE hold row.
- release then re-acquire works.
- expire_holds(now+delta) -> AVAILABLE + EXPIRED hold + event; twice is no-op.
- convert -> booking.unit_id set, hold CONVERTED, unit BOOKED.
- illegal transitions 409 (table-driven).
- cross-tenant hold/read attempts 404.
- bulk create collision reports per-row error, no partial commit for that row.
- extension limit (max 2).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.inventory import repository, service
from app.modules.inventory.exceptions import (
    DuplicateActiveHoldError,
    HoldExtensionLimitReachedError,
    HoldNotActiveError,
    HoldNotFoundError,
    InvalidUnitTransitionError,
    ProjectNotFoundError,
    UnitNotAvailableError,
    UnitNotFoundError,
)
from app.modules.inventory.models import (
    HoldState,
    PropertyUnit,
    UnitHold,
    UnitStatus,
    UnitStatusEvent,
)
from app.modules.inventory.schemas import UnitCreateRequest
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD


def _principal(user_id: UUID, tenant_id: UUID) -> SimpleNamespace:
    """Detached actor for worker threads (see test_receipt_integrity)."""

    return SimpleNamespace(id=user_id, tenant_id=tenant_id)


def _fixture(
    session: Session, *, slug: str | None = None
) -> tuple[Tenant, User, Project, Lead]:
    tenant = Tenant(slug=slug or f"inv-{uuid4().hex[:8]}", name="Inventory Co")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id, full_name="Inventory Admin",
        email=f"inv.{tenant.id.hex[:10]}@inventory.example",
        password_hash=hash_password(TEST_PASSWORD), role_id=role.id, is_active=True,
    )
    session.add(admin)
    session.flush()
    session.refresh(admin)  # ensure the role relationship resolves after commits
    project = Project(
        tenant_id=tenant.id, name="Canopy Towers", slug=f"canopy-{tenant.id.hex[:8]}",
        location="Pune", status=ProjectStatus.ACTIVE.value, created_by=admin.id,
    )
    session.add(project)
    session.flush()
    lead = Lead(
        tenant_id=tenant.id, full_name="Buyer One", email=f"buyer.{tenant.id.hex[:8]}@inv.example",
        phone=f"91{uuid4().int % 10**10:010d}", project_id=project.id,
        source=LeadSource.WEBSITE.value, status=LeadStatus.CONVERTED.value,
        consent_to_contact=True,
    )
    session.add(lead)
    session.commit()
    return tenant, admin, project, lead


def _available_unit(session: Session, admin: User, project: Project, code: str = "A-1204") -> PropertyUnit:
    return service.create_unit(
        session,
        actor=admin,
        payload=UnitCreateRequest(
            project_id=project.id, internal_code=code, configuration="3 BHK",
            carpet_area_sqft=1450, status=UnitStatus.AVAILABLE,
        ),
    )


class TestConcurrentHolds:
    def test_db_partial_unique_index_rejects_second_active_hold(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        """The invariant lives in the DB: even a direct ORM insert that skips
        the service layer cannot create a second ACTIVE hold on one unit."""

        from sqlalchemy.exc import IntegrityError

        with test_session_factory() as session:
            _tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            first = UnitHold(
                tenant_id=admin.tenant_id, unit_id=unit.id, owner_user_id=admin.id,
                lead_id=lead.id, expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
            session.add(first)
            session.commit()
            duplicate = UnitHold(
                tenant_id=admin.tenant_id, unit_id=unit.id, owner_user_id=admin.id,
                lead_id=lead.id, expires_at=datetime.now(UTC) + timedelta(hours=2),
            )
            session.add(duplicate)
            with pytest.raises(IntegrityError):
                session.flush()
            session.rollback()

            # Once the original hold leaves ACTIVE, a fresh ACTIVE row is
            # allowed; the partial index only ever excludes a second ACTIVE.
            first.state = HoldState.RELEASED.value
            session.add(first)
            session.commit()
            replacement = UnitHold(
                tenant_id=admin.tenant_id, unit_id=unit.id, owner_user_id=admin.id,
                lead_id=lead.id, expires_at=datetime.now(UTC) + timedelta(hours=3),
            )
            session.add(replacement)
            session.commit()
            assert session.scalar(
                select(func.count()).select_from(UnitHold).where(UnitHold.unit_id == unit.id)
            ) == 2

    def test_twenty_concurrent_acquires_exactly_one_winner(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            principal = _principal(admin.id, admin.tenant_id)
            unit_id, lead_id = unit.id, lead.id

        def acquire(index: int) -> str:
            # Distinct owners per thread would need distinct users; the unique
            # index is per (tenant, unit) so any actor set still races on the
            # same unit. Distinct sessions prove the DB-level backstop.
            with test_session_factory() as worker:
                try:
                    service.acquire_hold(
                        worker, actor=principal, unit_id=unit_id, lead_id=lead_id,
                        hours=48, reason=f"racer-{index}",
                    )
                    return "acquired"
                except HTTPException as exc:
                    assert exc.status_code == 409, exc
                    return "conflict"

        with ThreadPoolExecutor(max_workers=20) as pool:
            outcomes = list(pool.map(acquire, range(20)))

        assert outcomes.count("acquired") == 1, outcomes
        assert outcomes.count("conflict") == 19
        with test_session_factory() as session:
            assert session.scalar(
                select(func.count()).select_from(UnitHold).where(
                    UnitHold.unit_id == unit_id, UnitHold.state == HoldState.ACTIVE.value
                )
            ) == 1
            assert session.scalar(
                select(func.count()).select_from(UnitHold).where(UnitHold.unit_id == unit_id)
            ) == 1
            refreshed = session.get(PropertyUnit, unit_id)
            assert refreshed.status == UnitStatus.ON_HOLD.value

    def test_release_then_reacquire(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            first = service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id)
            service.release_hold(session, actor=admin, hold_id=first.id, reason="Buyer backed out.")
            session.refresh(unit)
            assert unit.status == UnitStatus.AVAILABLE.value

            second = service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id)
            assert second.id != first.id
            assert second.state == HoldState.ACTIVE.value
            assert unit.status == UnitStatus.ON_HOLD.value
            assert session.scalar(
                select(func.count()).select_from(UnitHold).where(UnitHold.unit_id == unit.id)
            ) == 2

    def test_acquire_on_held_unit_is_409(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id)
            with pytest.raises(UnitNotAvailableError) as exc:
                service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id)
            assert exc.value.status_code == 409
            assert "ON_HOLD" in str(exc.value.detail)


class TestExpiry:
    def test_expire_then_noop_and_event(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            hold = service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id)

            future = datetime.now(UTC) + timedelta(hours=49)
            assert service.expire_holds(session, future) == 1
            session.refresh(hold)
            session.refresh(unit)
            assert hold.state == HoldState.EXPIRED.value
            assert hold.release_source == "EXPIRY"
            assert unit.status == UnitStatus.AVAILABLE.value
            events = repository.status_history(session, unit.id, tenant_id=admin.tenant_id)
            assert [(e.from_status, e.to_status) for e in events] == [
                ("AVAILABLE", "ON_HOLD"), ("ON_HOLD", "AVAILABLE")
            ]
            assert events[-1].reason == "Hold expired."

            # Second run at the same or later instant is a no-op.
            assert service.expire_holds(session, future + timedelta(days=1)) == 0
            assert session.scalar(select(func.count()).select_from(UnitStatusEvent)) == 2

    def test_unexpired_holds_untouched(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id, hours=48)
            assert service.expire_holds(session, datetime.now(UTC) + timedelta(hours=1)) == 0

    def test_acquire_auto_expires_stale_hold(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        """An ON_HOLD unit whose ACTIVE hold is past expiry can be re-claimed:
        the stale hold is expired inside the acquiring transaction rather than
        forcing a scheduler pass first."""

        with test_session_factory() as session:
            _tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            stale = service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id, hours=1)
            stale.expires_at = datetime.now(UTC) - timedelta(minutes=5)
            session.commit()

            fresh = service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id, hours=24)
            assert fresh.id != stale.id
            assert fresh.state == HoldState.ACTIVE.value
            session.refresh(stale)
            assert stale.state == HoldState.EXPIRED.value
            assert stale.release_source == "EXPIRY"
            assert unit.status == UnitStatus.ON_HOLD.value
            assert session.scalar(
                select(func.count()).select_from(UnitHold).where(
                    UnitHold.unit_id == unit.id, UnitHold.state == HoldState.ACTIVE.value
                )
            ) == 1


class TestConversion:
    def test_expired_hold_cannot_convert(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            hold = service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id, hours=1)
            hold.expires_at = datetime.now(UTC) - timedelta(minutes=1)
            session.commit()
            with pytest.raises(HoldNotActiveError):
                service.convert_to_booking(
                    session, actor=admin, hold_id=hold.id, consideration_paise=1000
                )

    def test_expired_hold_cannot_reserve(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            hold = service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id, hours=1)
            hold.expires_at = datetime.now(UTC) - timedelta(minutes=1)
            session.commit()
            with pytest.raises(HoldNotActiveError):
                service.reserve_unit(session, actor=admin, hold_id=hold.id)

    def test_convert_creates_booking_with_unit_id(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            hold = service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id)

            converted, booking = service.convert_to_booking(
                session, actor=admin, hold_id=hold.id, consideration_paise=1_50_00_00_00
            )
            assert booking.unit_id == unit.id
            assert booking.unit_number == "A-1204"
            assert booking.configuration == "3 BHK"
            assert converted.state == HoldState.CONVERTED.value
            assert converted.converted_booking_id == booking.id
            assert converted.release_source == "CONVERTED"
            assert unit.status == UnitStatus.BOOKED.value

            with pytest.raises(HoldNotActiveError):
                service.convert_to_booking(
                    session, actor=admin, hold_id=hold.id, consideration_paise=1000
                )

    def test_reserve_then_convert(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            hold = service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id)
            service.reserve_unit(session, actor=admin, hold_id=hold.id)
            assert unit.status == UnitStatus.RESERVED.value
            _hold, booking = service.convert_to_booking(
                session, actor=admin, hold_id=hold.id, consideration_paise=1000
            )
            assert booking.unit_id == unit.id
            assert unit.status == UnitStatus.BOOKED.value


class TestTransitionMap:
    @pytest.mark.parametrize(
        ("start", "end"),
        [
            (UnitStatus.DRAFT, UnitStatus.ON_HOLD),
            (UnitStatus.DRAFT, UnitStatus.BOOKED),
            (UnitStatus.AVAILABLE, UnitStatus.RESERVED),
            (UnitStatus.AVAILABLE, UnitStatus.BOOKED),
            (UnitStatus.AVAILABLE, UnitStatus.SOLD),
            (UnitStatus.ON_HOLD, UnitStatus.SOLD),
            (UnitStatus.BOOKED, UnitStatus.ON_HOLD),
            (UnitStatus.SOLD, UnitStatus.AVAILABLE),
            (UnitStatus.CANCELLED, UnitStatus.AVAILABLE),
            (UnitStatus.RESERVED, UnitStatus.DRAFT),
        ],
    )
    def test_illegal_transitions_are_409(
        self, test_session_factory: sessionmaker[Session], start: UnitStatus, end: UnitStatus
    ) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, _lead = _fixture(session)
            unit = service.create_unit(
                session, actor=admin,
                payload=UnitCreateRequest(project_id=project.id, internal_code="X-1", status=UnitStatus.DRAFT),
            )
            # Force the starting state without using the transition map.
            unit.status = start.value
            session.commit()
            with pytest.raises(InvalidUnitTransitionError) as exc:
                service.transition_unit(session, actor=admin, unit_id=unit.id, to_status=end, reason="nope")
            assert exc.value.status_code == 409
            assert unit.status == start.value

    def test_manual_hold_entry_is_rejected_even_on_available(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, _lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            with pytest.raises(InvalidUnitTransitionError):
                service.transition_unit(
                    session, actor=admin, unit_id=unit.id, to_status=UnitStatus.ON_HOLD, reason="manual hold"
                )

    def test_blocked_requires_approval_flag(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, _lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            with pytest.raises(HTTPException) as exc:
                service.transition_unit(
                    session, actor=admin, unit_id=unit.id, to_status=UnitStatus.BLOCKED, reason="compliance"
                )
            assert exc.value.status_code == 400
            service.transition_unit(
                session, actor=admin, unit_id=unit.id, to_status=UnitStatus.BLOCKED,
                reason="compliance", approved=True,
            )
            assert unit.status == UnitStatus.BLOCKED.value

    def test_legal_admin_lifecycle(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, _lead = _fixture(session)
            unit = service.create_unit(
                session, actor=admin,
                payload=UnitCreateRequest(project_id=project.id, internal_code="L-1", status=UnitStatus.DRAFT),
            )
            service.transition_unit(session, actor=admin, unit_id=unit.id, to_status=UnitStatus.APPROVED, reason="ok")
            service.transition_unit(session, actor=admin, unit_id=unit.id, to_status=UnitStatus.AVAILABLE, reason="publish")
            assert unit.status == UnitStatus.AVAILABLE.value
            events = repository.status_history(session, unit.id, tenant_id=admin.tenant_id)
            assert [e.to_status for e in events] == ["APPROVED", "AVAILABLE"]


class TestTenantIsolation:
    def test_cross_tenant_hold_and_read_are_404(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            _ta, admin_a, project_a, lead_a = _fixture(session, slug="inv-a")
            unit = _available_unit(session, admin_a, project_a)
            _tb, admin_b, project_b, lead_b = _fixture(session, slug="inv-b")

            with pytest.raises(UnitNotFoundError) as exc:
                service.acquire_hold(session, actor=admin_b, unit_id=unit.id, lead_id=lead_b.id)
            assert exc.value.status_code == 404
            with pytest.raises(UnitNotFoundError):
                service.transition_unit(
                    session, actor=admin_b, unit_id=unit.id, to_status=UnitStatus.BLOCKED,
                    reason="cross-tenant", approved=True,
                )
            with pytest.raises(ProjectNotFoundError):
                service.availability_summary(session, tenant_id=admin_b.tenant_id, project_id=project_a.id)

            hold = service.acquire_hold(session, actor=admin_a, unit_id=unit.id, lead_id=lead_a.id)
            with pytest.raises(HoldNotFoundError):
                service.release_hold(session, actor=admin_b, hold_id=hold.id, reason="not mine")
            with pytest.raises(HoldNotFoundError):
                service.reserve_unit(session, actor=admin_b, hold_id=hold.id)

    def test_other_owner_cannot_release(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            hold = service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id)
            other = User(
                tenant_id=tenant.id, full_name="Other", email=f"other.{uuid4().hex[:8]}@inv.example",
                password_hash=hash_password(TEST_PASSWORD), role_id=admin.role_id, is_active=True,
            )
            sales_role = Role(name=RoleName.SALES_EXECUTIVE.value)
            session.add(sales_role)
            session.flush()
            other.role_id = sales_role.id  # non-admin peer: must not release someone else's hold
            session.add(other)
            session.commit()
            with pytest.raises(HTTPException) as exc:
                service.release_hold(session, actor=other, hold_id=hold.id, reason="not mine")
            assert exc.value.status_code == 403


class TestBulkCreate:
    def test_collision_reports_row_and_does_not_commit_it(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, _lead = _fixture(session)
            _available_unit(session, admin, project, code="A-1204")

            results = service.bulk_create_units(
                session,
                actor=admin,
                rows=[
                    UnitCreateRequest(project_id=project.id, internal_code="A-1204"),
                    UnitCreateRequest(project_id=project.id, internal_code="A-1205"),
                    UnitCreateRequest(project_id=project.id, internal_code="A-1206"),
                ],
            )
            assert [r.ok for r in results] == [False, True, True]
            assert "exists" in results[0].reason
            codes = set(session.scalars(select(PropertyUnit.internal_code)).all())
            assert codes == {"A-1204", "A-1205", "A-1206"}

    def test_duplicate_within_batch(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, _lead = _fixture(session)
            results = service.bulk_create_units(
                session,
                actor=admin,
                rows=[
                    UnitCreateRequest(project_id=project.id, internal_code="B-1"),
                    UnitCreateRequest(project_id=project.id, internal_code="B-1"),
                ],
            )
            assert [r.ok for r in results] == [True, False]
            assert "batch" in results[1].reason
            assert session.scalar(select(func.count()).select_from(PropertyUnit)) == 1

    def test_dry_run_commits_nothing(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, _lead = _fixture(session)
            results = service.bulk_create_units(
                session,
                actor=admin,
                rows=[UnitCreateRequest(project_id=project.id, internal_code="D-1")],
                dry_run=True,
            )
            assert results[0].ok
            assert session.scalar(select(func.count()).select_from(PropertyUnit)) == 0

    def test_bad_project_row_isolated(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, _lead = _fixture(session)
            results = service.bulk_create_units(
                session,
                actor=admin,
                rows=[
                    UnitCreateRequest(project_id=uuid4(), internal_code="Z-1"),
                    UnitCreateRequest(project_id=project.id, internal_code="Z-2"),
                ],
            )
            assert [r.ok for r in results] == [False, True]
            assert "Project not found" in results[0].reason
            assert set(session.scalars(select(PropertyUnit.internal_code)).all()) == {"Z-2"}


class TestExtensions:
    def test_extension_limit(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            hold = service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id)
            first_expiry = hold.expires_at

            service.extend_hold(session, actor=admin, hold_id=hold.id, hours=12)
            assert hold.extension_count == 1
            assert hold.expires_at > first_expiry
            service.extend_hold(session, actor=admin, hold_id=hold.id, hours=12)
            assert hold.extension_count == 2
            with pytest.raises(HoldExtensionLimitReachedError) as exc:
                service.extend_hold(session, actor=admin, hold_id=hold.id, hours=12)
            assert exc.value.status_code == 409

    def test_extend_inactive_hold_rejected(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project)
            hold = service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id)
            service.release_hold(session, actor=admin, hold_id=hold.id, reason="done")
            with pytest.raises(HoldNotActiveError):
                service.extend_hold(session, actor=admin, hold_id=hold.id, hours=12)


class TestUnitCrud:
    def test_non_positive_area_is_400(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, _lead = _fixture(session)
            with pytest.raises(HTTPException) as exc:
                service.create_unit(
                    session, actor=admin,
                    payload=UnitCreateRequest.model_construct(
                        project_id=project.id, internal_code="NEG-1", carpet_area_sqft=-10,
                        configuration=None, floor=None, position=None, tower=None,
                        built_up_area_sqft=None, plot_number=None, facing=None, views=None,
                        saleable=True, status=UnitStatus.DRAFT, status_reason=None,
                        rera_disclosure_json={},
                    ),
                )
            assert exc.value.status_code == 400
            assert session.scalar(select(func.count()).select_from(PropertyUnit)) == 0

    def test_duplicate_code_is_409(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, _lead = _fixture(session)
            _available_unit(session, admin, project, code="C-1")
            with pytest.raises(HTTPException) as exc:
                _available_unit(session, admin, project, code="C-1")
            assert exc.value.status_code == 409

    def test_same_code_allowed_in_other_project_and_tenant(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            _tenant, admin, project, _lead = _fixture(session, slug="t-one")
            _available_unit(session, admin, project, code="S-1")
            other_project = Project(
                tenant_id=admin.tenant_id, name="Second", slug="second", location="Goa",
                status=ProjectStatus.ACTIVE.value, created_by=admin.id,
            )
            session.add(other_project)
            session.commit()
            _available_unit(session, admin, other_project, code="S-1")
            _tb, admin_b, project_b, _lb = _fixture(session, slug="t-two")
            _available_unit(session, admin_b, project_b, code="S-1")
            assert session.scalar(select(func.count()).select_from(PropertyUnit)) == 3

    def test_availability_summary_counts(self, test_session_factory: sessionmaker[Session]) -> None:
        with test_session_factory() as session:
            tenant, admin, project, lead = _fixture(session)
            unit = _available_unit(session, admin, project, code="V-1")
            _available_unit(session, admin, project, code="V-2")
            service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id)
            summary = service.availability_summary(session, tenant_id=tenant.id, project_id=project.id)
            assert summary["counts"][UnitStatus.AVAILABLE.value] == 1
            assert summary["counts"][UnitStatus.ON_HOLD.value] == 1
            assert summary["total"] == 2
