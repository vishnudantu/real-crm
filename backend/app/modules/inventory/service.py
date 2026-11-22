"""Inventory business logic: units, availability state machine, atomic holds.

Concurrency contract (mirrors postsales.record_receipt):
- PostgreSQL serializes hold acquisition with a transaction-scoped advisory
  lock keyed by (tenant, unit); the partial unique index on ACTIVE holds is
  the database backstop. Both run in one transaction with the status change.
- SQLite (isolated tests) uses a process lock plus the shared StaticPool
  connection; the same partial unique index still guards the invariant.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.inventory import repository
from app.modules.inventory.exceptions import (
    BulkCreateRowError,
    DuplicateActiveHoldError,
    HoldExtensionLimitReachedError,
    HoldNotActiveError,
    HoldNotFoundError,
    HoldNotOwnedByActorError,
    InvalidUnitTransitionError,
    ProjectNotFoundError,
    UnitCodeAlreadyExistsError,
    UnitNotAvailableError,
    UnitNotFoundError,
)
from app.modules.inventory.models import (
    HoldReleaseSource,
    HoldState,
    PropertyUnit,
    UnitEventSource,
    UnitHold,
    UnitStatus,
    UnitStatusEvent,
)
from app.modules.inventory.schemas import (
    BulkRowResult,
    UnitCreateRequest,
    UnitUpdateRequest,
)
from app.modules.leads.models import Lead
from app.modules.projects.models import Project
from app.modules.users.models import RoleName

_sqlite_hold_lock = Lock()

DEFAULT_HOLD_HOURS = 48
MAX_HOLD_EXTENSIONS = 2

# Explicit transition map. Every edge is gated by event source so that holds,
# reservations, and bookings can only be entered through their own services:
# - DRAFT -> APPROVED: admin approval of a new unit.
# - APPROVED -> AVAILABLE: admin publishes the unit for sale.
# - AVAILABLE -> ON_HOLD: acquire_hold only (HOLD).
# - ON_HOLD -> AVAILABLE: release_hold / expire_holds only (HOLD).
# - ON_HOLD -> RESERVED: reserve_unit only (HOLD).
# - ON_HOLD/RESERVED -> BOOKED: convert_to_booking only (BOOKING).
# - BOOKED -> SOLD: payments service later; admin with reason for now (MANUAL).
# - BOOKED -> AVAILABLE: booking cancellation releases the unit (CANCELLATION).
# - AVAILABLE/ON_HOLD -> BLOCKED: admin with approved=True (MANUAL).
# - BLOCKED/UNDER_DISPUTE -> AVAILABLE: admin resolution with reason (MANUAL).
# - BOOKED/SOLD -> UNDER_DISPUTE and DRAFT/APPROVED/AVAILABLE/BLOCKED/
#   UNDER_DISPUTE -> CANCELLED: admin with reason (MANUAL).
# CANCELLED is terminal; RELEASED is not a unit status — release returns the
# unit to AVAILABLE and is recorded on the hold + status event instead.
ALLOWED_TRANSITIONS: dict[UnitStatus, dict[UnitStatus, frozenset[UnitEventSource]]] = {
    UnitStatus.DRAFT: {
        UnitStatus.APPROVED: frozenset({UnitEventSource.MANUAL}),
        UnitStatus.CANCELLED: frozenset({UnitEventSource.MANUAL}),
    },
    UnitStatus.APPROVED: {
        UnitStatus.AVAILABLE: frozenset({UnitEventSource.MANUAL}),
        UnitStatus.CANCELLED: frozenset({UnitEventSource.MANUAL}),
    },
    UnitStatus.AVAILABLE: {
        UnitStatus.ON_HOLD: frozenset({UnitEventSource.HOLD}),
        UnitStatus.BLOCKED: frozenset({UnitEventSource.MANUAL}),
        UnitStatus.UNDER_DISPUTE: frozenset({UnitEventSource.MANUAL}),
        UnitStatus.CANCELLED: frozenset({UnitEventSource.MANUAL}),
    },
    UnitStatus.ON_HOLD: {
        UnitStatus.AVAILABLE: frozenset({UnitEventSource.HOLD}),
        UnitStatus.RESERVED: frozenset({UnitEventSource.HOLD}),
        UnitStatus.BOOKED: frozenset({UnitEventSource.BOOKING}),
        UnitStatus.BLOCKED: frozenset({UnitEventSource.MANUAL}),
    },
    UnitStatus.RESERVED: {
        UnitStatus.BOOKED: frozenset({UnitEventSource.BOOKING}),
        UnitStatus.AVAILABLE: frozenset({UnitEventSource.HOLD}),
    },
    UnitStatus.BOOKED: {
        UnitStatus.SOLD: frozenset({UnitEventSource.MANUAL}),
        UnitStatus.AVAILABLE: frozenset({UnitEventSource.CANCELLATION}),
        UnitStatus.UNDER_DISPUTE: frozenset({UnitEventSource.MANUAL}),
    },
    UnitStatus.SOLD: {
        UnitStatus.UNDER_DISPUTE: frozenset({UnitEventSource.MANUAL}),
    },
    UnitStatus.BLOCKED: {
        UnitStatus.AVAILABLE: frozenset({UnitEventSource.MANUAL}),
        UnitStatus.CANCELLED: frozenset({UnitEventSource.MANUAL}),
    },
    UnitStatus.UNDER_DISPUTE: {
        UnitStatus.AVAILABLE: frozenset({UnitEventSource.MANUAL}),
        UnitStatus.BLOCKED: frozenset({UnitEventSource.MANUAL}),
        UnitStatus.CANCELLED: frozenset({UnitEventSource.MANUAL}),
    },
    UnitStatus.CANCELLED: {},
}

_MANUAL_REASON_REQUIRED = {
    UnitStatus.SOLD,
    UnitStatus.CANCELLED,
    UnitStatus.UNDER_DISPUTE,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; compare expiries in UTC on both backends."""

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _resolve_admin(session: Session, actor) -> bool:
    """Admin check that works for ORM users (possibly expired after commit)
    and for detached test principals carrying only id/tenant_id."""

    role = getattr(actor, "role", None)
    if role is not None:
        return getattr(role, "name", None) == RoleName.ADMIN.value
    if getattr(actor, "role_id", None) is None:
        return False
    from app.modules.users.models import Role

    return session.get(Role, actor.role_id).name == RoleName.ADMIN.value


def _source_value(source: UnitEventSource | str) -> UnitEventSource:
    return source if isinstance(source, UnitEventSource) else UnitEventSource(str(source).upper())


def _status_value(value: UnitStatus | str) -> UnitStatus:
    return value if isinstance(value, UnitStatus) else UnitStatus(str(value).upper())


def _get_unit_or_404(session: Session, unit_id: UUID, *, tenant_id: UUID) -> PropertyUnit:
    unit = repository.get_unit(session, unit_id, tenant_id=tenant_id)
    if unit is None:
        raise UnitNotFoundError()
    return unit


def _get_hold_or_404(session: Session, hold_id: UUID, *, tenant_id: UUID) -> UnitHold:
    hold = repository.get_hold(session, hold_id, tenant_id=tenant_id)
    if hold is None:
        raise HoldNotFoundError()
    return hold


def _require_owner_or_admin(session: Session, actor, hold: UnitHold) -> None:
    if not _resolve_admin(session, actor) and hold.owner_user_id != actor.id:
        raise HoldNotOwnedByActorError()


def _append_transition(
    session: Session,
    *,
    unit: PropertyUnit,
    to_status: UnitStatus,
    reason: str | None,
    source: UnitEventSource,
    actor_id: UUID | None,
    approved: bool = False,
    effective_at: datetime | None = None,
    meta: dict | None = None,
) -> UnitStatusEvent:
    """Validate and apply one edge, appending its event in the caller's tx."""

    from_status = UnitStatus(unit.status)
    allowed_sources = ALLOWED_TRANSITIONS.get(from_status, {}).get(to_status, frozenset())
    if source not in allowed_sources:
        raise InvalidUnitTransitionError(from_status.value, to_status.value)
    if to_status == UnitStatus.BLOCKED and source == UnitEventSource.MANUAL and not approved:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Blocking a unit requires approved=true."
        )
    if (
        source in (UnitEventSource.MANUAL, UnitEventSource.CANCELLATION)
        and to_status in _MANUAL_REASON_REQUIRED
        and not (reason or "").strip()
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"A reason is required to mark a unit {to_status.value}."
        )

    unit.status = to_status.value
    unit.status_reason = reason
    session.add(unit)
    event = UnitStatusEvent(
        tenant_id=unit.tenant_id,
        unit_id=unit.id,
        from_status=from_status.value,
        to_status=to_status.value,
        actor_user_id=actor_id,
        reason=reason,
        source=source.value,
        effective_at=effective_at or _now(),
        event_meta=meta or {},
    )
    session.add(event)
    session.flush()
    return event


def create_unit(
    session: Session, *, actor, payload: UnitCreateRequest, commit: bool = True
) -> PropertyUnit:
    """Create a canonical unit in a tenant project; codes are project-unique."""

    project = session.scalar(
        select(Project).where(Project.id == payload.project_id, Project.tenant_id == actor.tenant_id)
    )
    if project is None:
        raise ProjectNotFoundError()
    if repository.get_unit_by_code(
        session, payload.project_id, payload.internal_code, tenant_id=actor.tenant_id
    ) is not None:
        raise UnitCodeAlreadyExistsError()
    if payload.status not in (UnitStatus.DRAFT, UnitStatus.APPROVED, UnitStatus.AVAILABLE):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Units are created as DRAFT, APPROVED, or AVAILABLE; use the lifecycle endpoints afterwards.",
        )
    for area in (payload.carpet_area_sqft, payload.built_up_area_sqft):
        if area is not None and area <= 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Areas must be positive square feet."
            )

    unit = PropertyUnit(
        tenant_id=actor.tenant_id,
        project_id=payload.project_id,
        internal_code=payload.internal_code,
        configuration=payload.configuration,
        floor=payload.floor,
        position=payload.position,
        tower=payload.tower,
        carpet_area_sqft=payload.carpet_area_sqft,
        built_up_area_sqft=payload.built_up_area_sqft,
        plot_number=payload.plot_number,
        facing=payload.facing,
        views=payload.views,
        saleable=payload.saleable,
        status=payload.status.value,
        status_reason=payload.status_reason,
        rera_disclosure_json=payload.rera_disclosure_json,
    )
    session.add(unit)
    try:
        if commit:
            session.commit()
            session.refresh(unit)
        else:
            session.flush()
    except IntegrityError:
        session.rollback()
        raise UnitCodeAlreadyExistsError() from None
    return unit


def bulk_create_units(
    session: Session, *, actor, rows: list[UnitCreateRequest], dry_run: bool = False
) -> list[BulkRowResult]:
    """Validate and create many units with per-row isolation.

    Each row is flushed in its own SAVEPOINT: a colliding or invalid row is
    reported and rolled back without discarding its siblings. ``dry_run``
    performs the same validation (including duplicate detection against the
    database and within the batch) and rolls everything back.
    """

    results: list[BulkRowResult] = []
    seen: set[tuple[UUID, str]] = set()
    # Dry-run previews run inside an outer SAVEPOINT that is rolled back at the
    # end, so per-row ``begin_nested`` commits release only their inner
    # savepoint and nothing reaches the database permanently.
    outer = session.begin_nested() if dry_run else None
    for index, payload in enumerate(rows):
        key = (payload.project_id, payload.internal_code)
        try:
            if key in seen:
                raise BulkCreateRowError("Duplicate code within this batch for the project.")
            seen.add(key)
            with session.begin_nested():
                unit = create_unit(session, actor=actor, payload=payload, commit=False)
            results.append(
                BulkRowResult(index=index, internal_code=payload.internal_code, ok=True, unit_id=unit.id)
            )
        except BulkCreateRowError as exc:
            results.append(
                BulkRowResult(index=index, internal_code=payload.internal_code, ok=False, reason=exc.reason)
            )
        except HTTPException as exc:
            results.append(
                BulkRowResult(
                    index=index, internal_code=payload.internal_code, ok=False, reason=str(exc.detail)
                )
            )
    if outer is not None:
        outer.rollback()
    else:
        session.commit()
    return results


def transition_unit(
    session: Session,
    *,
    actor,
    unit_id: UUID,
    to_status: UnitStatus | str,
    reason: str | None,
    source: UnitEventSource | str = UnitEventSource.MANUAL,
    approved: bool = False,
) -> PropertyUnit:
    """Apply a validated manual/system transition and commit atomically."""

    unit = _get_unit_or_404(session, unit_id, tenant_id=actor.tenant_id)
    _append_transition(
        session,
        unit=unit,
        to_status=_status_value(to_status),
        reason=reason,
        source=_source_value(source),
        actor_id=actor.id,
        approved=approved,
    )
    session.commit()
    session.refresh(unit)
    return unit


def update_unit(
    session: Session, *, actor, unit_id: UUID, payload: UnitUpdateRequest
) -> PropertyUnit:
    """Edit mutable unit fields. ``internal_code`` is immutable (canonical id).

    Status transitions are deliberately not handled here; they go through
    ``transition_unit`` so the state machine and its event log stay authoritative.
    """
    unit = _get_unit_or_404(session, unit_id, tenant_id=actor.tenant_id)
    for field in (
        "configuration",
        "floor",
        "position",
        "tower",
        "carpet_area_sqft",
        "built_up_area_sqft",
        "plot_number",
        "facing",
        "views",
        "saleable",
        "rera_disclosure_json",
    ):
        if field in payload.model_fields_set:
            setattr(unit, field, getattr(payload, field))
    unit.updated_at = _now()
    session.add(unit)
    session.commit()
    session.refresh(unit)
    return unit


def delete_unit(session: Session, *, actor, unit_id: UUID) -> None:
    """Delete a DRAFT unit that has no holds or bookings (safe correction).

    A unit that has progressed beyond DRAFT, or that has any hold or a linked
    sale booking, cannot be deleted — its history must be preserved. Such units
    should be transitioned to CANCELLED via the state machine instead.
    """
    unit = _get_unit_or_404(session, unit_id, tenant_id=actor.tenant_id)
    if unit.status != UnitStatus.DRAFT.value:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only DRAFT units can be deleted; cancel the unit instead.",
        )
    has_hold = session.scalar(
        select(UnitHold.id).where(
            UnitHold.unit_id == unit.id, UnitHold.tenant_id == actor.tenant_id
        ).limit(1)
    )
    if has_hold is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot delete a unit that has a hold; release the hold first.",
        )
    from app.modules.postsales.models import SaleBooking

    has_booking = session.scalar(
        select(SaleBooking.id).where(
            SaleBooking.unit_id == unit.id, SaleBooking.tenant_id == actor.tenant_id
        ).limit(1)
    )
    if has_booking is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot delete a unit that is linked to a sale booking.",
        )
    session.delete(unit)
    session.commit()


def acquire_hold(
    session: Session,
    *,
    actor,
    unit_id: UUID,
    lead_id: UUID | None = None,
    opportunity_ref: str | None = None,
    hours: int = DEFAULT_HOLD_HOURS,
    reason: str | None = None,
) -> UnitHold:
    """Atomically claim an AVAILABLE unit and move it to ON_HOLD.

    Exactly one concurrent caller wins: the advisory/process lock serializes
    the availability check, and the partial unique index on ACTIVE holds is
    the final backstop (a lost race surfaces as 409, never a second hold).
    """

    if hours < 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Hold duration must be at least one hour.")

    def _acquire() -> UnitHold:
        repository.lock_unit_for_hold(session, tenant_id=actor.tenant_id, unit_id=unit_id)
        unit = _get_unit_or_404(session, unit_id, tenant_id=actor.tenant_id)
        existing = repository.active_hold_for_unit(session, unit_id, tenant_id=actor.tenant_id)
        if existing is not None and _as_utc(existing.expires_at) <= _now():
            # A stale hold must not strand a unit until the scheduler runs:
            # expire it inside this same locked transaction, then re-claim.
            _release(
                session,
                hold=existing,
                actor_id=None,
                reason="Hold expired.",
                state=HoldState.EXPIRED,
                release_source=HoldReleaseSource.EXPIRY,
                at=_now(),
            )
            existing = None
        if not unit.saleable or unit.status != UnitStatus.AVAILABLE.value:
            raise UnitNotAvailableError(unit.status)
        if existing is not None:
            raise DuplicateActiveHoldError()
        if lead_id is not None:
            lead = session.scalar(
                select(Lead).where(Lead.id == lead_id, Lead.tenant_id == actor.tenant_id)
            )
            if lead is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found.")
            if lead.project_id != unit.project_id:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "The lead and unit belong to different projects."
                )

        hold = UnitHold(
            tenant_id=actor.tenant_id,
            unit_id=unit.id,
            lead_id=lead_id,
            opportunity_ref=opportunity_ref,
            owner_user_id=actor.id,
            reason=reason,
            state=HoldState.ACTIVE.value,
            expires_at=_now() + timedelta(hours=hours),
        )
        session.add(hold)
        session.flush()  # id + the unique-index backstop fire here
        _append_transition(
            session,
            unit=unit,
            to_status=UnitStatus.ON_HOLD,
            reason=reason or "Unit held.",
            source=UnitEventSource.HOLD,
            actor_id=actor.id,
            meta={"hold_id": str(hold.id)},
        )
        session.commit()
        session.refresh(hold)
        return hold

    try:
        if session.get_bind().dialect.name == "sqlite":
            with _sqlite_hold_lock:
                return _acquire()
        return _acquire()
    except IntegrityError:
        session.rollback()
        raise DuplicateActiveHoldError() from None


def extend_hold(
    session: Session, *, actor, hold_id: UUID, hours: int = 24, reason: str | None = None
) -> UnitHold:
    """Extend an ACTIVE hold owned by the actor; at most two extensions."""

    if hours < 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Extension must be at least one hour.")

    def _extend() -> UnitHold:
        hold = _get_hold_or_404(session, hold_id, tenant_id=actor.tenant_id)
        repository.lock_unit_for_hold(session, tenant_id=actor.tenant_id, unit_id=hold.unit_id)
        session.refresh(hold)
        _require_owner_or_admin(session, actor, hold)
        if hold.state != HoldState.ACTIVE.value or _as_utc(hold.expires_at) <= _now():
            raise HoldNotActiveError()
        if hold.extension_count >= MAX_HOLD_EXTENSIONS:
            raise HoldExtensionLimitReachedError()
        hold.extension_count += 1
        hold.expires_at = _as_utc(hold.expires_at) + timedelta(hours=hours)
        if reason:
            hold.reason = reason
        session.add(hold)
        session.commit()
        session.refresh(hold)
        return hold

    if session.get_bind().dialect.name == "sqlite":
        with _sqlite_hold_lock:
            return _extend()
    return _extend()


def _release(
    session: Session,
    *,
    hold: UnitHold,
    actor_id: UUID | None,
    reason: str,
    state: HoldState,
    release_source: HoldReleaseSource,
    at: datetime,
) -> UnitHold:
    unit = _get_unit_or_404(session, hold.unit_id, tenant_id=hold.tenant_id)
    hold.state = state.value
    hold.released_at = at
    hold.release_source = release_source.value
    session.add(hold)
    if unit.status in (UnitStatus.ON_HOLD.value, UnitStatus.RESERVED.value):
        _append_transition(
            session,
            unit=unit,
            to_status=UnitStatus.AVAILABLE,
            reason=reason,
            source=UnitEventSource.HOLD,
            actor_id=actor_id,
            effective_at=at,
            meta={"hold_id": str(hold.id), "release_source": release_source.value},
        )
    return hold


def release_hold(
    session: Session, *, actor, hold_id: UUID, reason: str
) -> UnitHold:
    """Release an ACTIVE hold (owner or admin) and return the unit to AVAILABLE."""

    if not (reason or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A release reason is required.")

    def _do_release() -> UnitHold:
        hold = _get_hold_or_404(session, hold_id, tenant_id=actor.tenant_id)
        repository.lock_unit_for_hold(session, tenant_id=actor.tenant_id, unit_id=hold.unit_id)
        session.refresh(hold)
        _require_owner_or_admin(session, actor, hold)
        if hold.state != HoldState.ACTIVE.value:
            raise HoldNotActiveError()
        _release(
            session,
            hold=hold,
            actor_id=actor.id,
            reason=reason,
            state=HoldState.RELEASED,
            release_source=HoldReleaseSource.MANUAL,
            at=_now(),
        )
        session.commit()
        session.refresh(hold)
        return hold

    if session.get_bind().dialect.name == "sqlite":
        with _sqlite_hold_lock:
            return _do_release()
    return _do_release()


def expire_holds(session: Session, now: datetime) -> int:
    """Expire every ACTIVE hold past its deadline; return the count expired.

    Idempotent: only ACTIVE rows with ``expires_at <= now`` are touched, each
    producing its own EXPIRED hold + ON_HOLD/RESERVED -> AVAILABLE event. A
    second run is a no-op. Exposed for a scheduler to call; not auto-wired.
    """

    candidates = repository.expired_active_holds(session, now=_as_utc(now))
    expired = 0

    def _expire_all() -> int:
        count = 0
        for candidate in candidates:
            repository.lock_unit_for_hold(
                session, tenant_id=candidate.tenant_id, unit_id=candidate.unit_id
            )
            hold = _get_hold_or_404(session, candidate.id, tenant_id=candidate.tenant_id)
            if hold.state != HoldState.ACTIVE.value or _as_utc(hold.expires_at) > _as_utc(now):
                continue
            _release(
                session,
                hold=hold,
                actor_id=None,
                reason="Hold expired.",
                state=HoldState.EXPIRED,
                release_source=HoldReleaseSource.EXPIRY,
                at=_as_utc(now),
            )
            count += 1
        session.commit()
        return count

    if session.get_bind().dialect.name == "sqlite":
        with _sqlite_hold_lock:
            expired = _expire_all()
    else:
        expired = _expire_all()
    return expired


def reserve_unit(session: Session, *, actor, hold_id: UUID) -> PropertyUnit:
    """Move an ACTIVE hold's unit ON_HOLD -> RESERVED; the hold stays exclusive."""

    def _reserve() -> PropertyUnit:
        hold = _get_hold_or_404(session, hold_id, tenant_id=actor.tenant_id)
        repository.lock_unit_for_hold(session, tenant_id=actor.tenant_id, unit_id=hold.unit_id)
        session.refresh(hold)
        _require_owner_or_admin(session, actor, hold)
        if hold.state != HoldState.ACTIVE.value or _as_utc(hold.expires_at) <= _now():
            raise HoldNotActiveError()
        unit = _get_unit_or_404(session, hold.unit_id, tenant_id=actor.tenant_id)
        if unit.status != UnitStatus.ON_HOLD.value:
            raise InvalidUnitTransitionError(unit.status, UnitStatus.RESERVED.value)
        _append_transition(
            session,
            unit=unit,
            to_status=UnitStatus.RESERVED,
            reason="Unit reserved from hold.",
            source=UnitEventSource.HOLD,
            actor_id=actor.id,
            meta={"hold_id": str(hold.id)},
        )
        session.commit()
        session.refresh(unit)
        return unit

    if session.get_bind().dialect.name == "sqlite":
        with _sqlite_hold_lock:
            return _reserve()
    return _reserve()


def convert_to_booking(
    session: Session,
    *,
    actor,
    hold_id: UUID,
    consideration_paise: int,
    booked_on=None,
) -> tuple[UnitHold, object]:
    """Convert an ACTIVE hold into a SaleBooking in one transaction.

    Creates the booking through postsales.create_booking (commit=False), marks
    the hold CONVERTED, and moves the unit ON_HOLD/RESERVED -> BOOKED. Any
    failure rolls back all three mutations together.
    """

    from app.modules.postsales.schemas import SaleBookingCreateRequest
    from app.modules.postsales.service import create_booking

    def _convert() -> tuple[UnitHold, object]:
        hold = _get_hold_or_404(session, hold_id, tenant_id=actor.tenant_id)
        repository.lock_unit_for_hold(session, tenant_id=actor.tenant_id, unit_id=hold.unit_id)
        session.refresh(hold)
        _require_owner_or_admin(session, actor, hold)
        if hold.state != HoldState.ACTIVE.value or _as_utc(hold.expires_at) <= _now():
            raise HoldNotActiveError()
        if hold.lead_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "A hold needs a lead before it can become a booking."
            )
        unit = _get_unit_or_404(session, hold.unit_id, tenant_id=actor.tenant_id)
        if unit.status not in (UnitStatus.ON_HOLD.value, UnitStatus.RESERVED.value):
            raise UnitNotAvailableError(unit.status)

        booking = create_booking(
            session,
            actor=actor,
            payload=SaleBookingCreateRequest(
                lead_id=hold.lead_id,
                unit_id=unit.id,
                unit_number=unit.internal_code,
                configuration=unit.configuration,
                carpet_area_sqft=unit.carpet_area_sqft,
                consideration_paise=consideration_paise,
                booked_on=booked_on,
            ),
            commit=False,
        )
        now = _now()
        hold.state = HoldState.CONVERTED.value
        hold.converted_booking_id = booking.id
        hold.released_at = now
        hold.release_source = HoldReleaseSource.CONVERTED.value
        session.add(hold)
        _append_transition(
            session,
            unit=unit,
            to_status=UnitStatus.BOOKED,
            reason="Hold converted to booking.",
            source=UnitEventSource.BOOKING,
            actor_id=actor.id,
            meta={"hold_id": str(hold.id), "booking_id": str(booking.id)},
        )
        session.commit()
        session.refresh(hold)
        return hold, booking

    if session.get_bind().dialect.name == "sqlite":
        with _sqlite_hold_lock:
            return _convert()
    return _convert()


def availability_summary(session: Session, *, tenant_id: UUID, project_id: UUID) -> dict:
    """Counts by status for one tenant project; cross-tenant reads are 404."""

    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
    )
    if project is None:
        raise ProjectNotFoundError()
    counts = {status_value.value: 0 for status_value in UnitStatus}
    counts.update(repository.availability_counts(session, project_id, tenant_id=tenant_id))
    return {"project_id": project_id, "counts": counts, "total": sum(counts.values())}
