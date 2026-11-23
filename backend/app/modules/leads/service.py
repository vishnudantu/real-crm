"""Lead intake, duplicate detection, assignment, and lifecycle logic."""

from __future__ import annotations

import hashlib
import logging
from threading import Lock
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.modules.leads import repository
from app.modules.leads.exceptions import (
    DuplicateLeadError,
    InvalidBudgetRangeError,
    InvalidLeadExecutiveError,
    InvalidLeadStatusTransitionError,
    LeadAssignmentConflictError,
    LeadConsentRequiredError,
    LeadFieldAccessDeniedError,
    LeadNotFoundError,
)
from app.modules.leads.models import (
    Lead,
    LeadAssignment,
    LeadSource,
    LeadStatus,
    utcnow,
)
from app.modules.leads.schemas import (
    DuplicateCheckResponse,
    LeadAssignmentListResponse,
    LeadAssignmentResponse,
    LeadAssignRequest,
    LeadCreateRequest,
    LeadListResponse,
    LeadOptOutRequest,
    LeadResponse,
    LeadStatusUpdateRequest,
    LeadUpdateRequest,
)
from app.modules.projects.exceptions import ProjectNotFoundError
from app.modules.projects.models import Project, ProjectStatus
from app.modules.projects.repository import get_project_by_id
from app.modules.tenancy.exceptions import TenantSuspendedError
from app.modules.tenancy.models import Tenant, TenantStatus
from app.modules.users import repository as users_repository
from app.modules.users.exceptions import InsufficientPermissionsError
from app.modules.users.models import RoleName, User

_ALLOWED_STATUS_TRANSITIONS: dict[LeadStatus, frozenset[LeadStatus]] = {
    LeadStatus.NEW: frozenset(
        {
            LeadStatus.CONTACTED,
            LeadStatus.QUALIFIED,
            LeadStatus.NOT_INTERESTED,
            LeadStatus.LOST,
        }
    ),
    LeadStatus.CONTACTED: frozenset(
        {
            LeadStatus.QUALIFIED,
            LeadStatus.NOT_INTERESTED,
            LeadStatus.VISIT_BOOKED,
            LeadStatus.LOST,
        }
    ),
    LeadStatus.QUALIFIED: frozenset(
        {
            LeadStatus.VISIT_BOOKED,
            LeadStatus.NOT_INTERESTED,
            LeadStatus.LOST,
        }
    ),
    LeadStatus.VISIT_BOOKED: frozenset(
        {
            LeadStatus.VISITED,
            LeadStatus.VISIT_CANCELLED,
            LeadStatus.NOT_INTERESTED,
            LeadStatus.LOST,
        }
    ),
    LeadStatus.VISIT_CANCELLED: frozenset(
        {
            LeadStatus.VISIT_BOOKED,
            LeadStatus.NOT_INTERESTED,
            LeadStatus.LOST,
        }
    ),
    LeadStatus.VISITED: frozenset(
        {
            LeadStatus.CONVERTED,
            LeadStatus.NOT_INTERESTED,
            LeadStatus.LOST,
        }
    ),
    LeadStatus.CONVERTED: frozenset(),
    LeadStatus.NOT_INTERESTED: frozenset(),
    LeadStatus.LOST: frozenset(),
}

_CONTACT_REQUIRING_STATUSES = frozenset(
    {
        LeadStatus.CONTACTED,
        LeadStatus.QUALIFIED,
        LeadStatus.VISIT_BOOKED,
        LeadStatus.VISITED,
        LeadStatus.CONVERTED,
    }
)

_SALES_ADMIN_ONLY_FIELDS = frozenset({"project_id", "source"})
_LEAD_MANAGER_ROLES = frozenset(
    {RoleName.ADMIN.value, RoleName.SALES_EXECUTIVE.value}
)


def _is_admin(user: User) -> bool:
    return user.role.name == RoleName.ADMIN.value


def _require_lead_manager(user: User) -> None:
    if user.role.name not in _LEAD_MANAGER_ROLES:
        raise InsufficientPermissionsError()


def _require_admin(user: User) -> None:
    """Capability gate for admin-only lead management surfaces.

    Built-in ADMIN passes by role; a custom role passes with an explicit
    leads.manage grant. Row-level scoping elsewhere still uses ``_is_admin``
    on the built-in base role only.
    """
    from app.modules.auth.dependencies import has_permission
    from app.modules.users.permissions import LEADS_MANAGE

    if _is_admin(user) or has_permission(user, LEADS_MANAGE):
        return
    raise InsufficientPermissionsError()


def _pages(total: int, page_size: int) -> int:
    return (total + page_size - 1) // page_size if total else 0


def _project_is_active(
    session: Session,
    project_id: UUID,
    *,
    tenant_id: UUID,
) -> Project:
    """Return an active project inside the tenant, or raise ProjectNotFoundError."""

    # SQLite in-memory (used by the isolated test suite) with concurrent
    # threads can return stale snapshots. Expire all cached instances so the
    # query fetches fresh data from the database.
    session.expire_all()
    project = get_project_by_id(session, project_id, tenant_id=tenant_id)
    if project is None or project.status != ProjectStatus.ACTIVE.value:
        raise ProjectNotFoundError()
    return project


def _resolve_active_project_any_tenant(session: Session, project_id: UUID) -> Project:
    """Public intake: locate an active project by id to derive the owning tenant.

    Project ids are globally unique UUIDs so this read is safe to run unscoped;
    the tenant status is validated immediately afterwards and all subsequent
    operations are tenant-scoped. No tenancy information leaks in errors.
    """

    from sqlalchemy import select

    session.expire_all()
    project = session.scalar(
        select(Project).where(Project.id == project_id)
    )
    if project is None or project.status != ProjectStatus.ACTIVE.value:
        raise ProjectNotFoundError()
    tenant = session.get(Tenant, project.tenant_id)
    if tenant is None or tenant.status != TenantStatus.ACTIVE.value:
        raise TenantSuspendedError()
    return project


def _advisory_key(prefix: str, value: str, *, tenant_id: UUID) -> int:
    digest = hashlib.blake2b(
        f"{tenant_id}:{prefix}:{value}".encode(),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, "big", signed=True)


def _lock_contact_keys(
    session: Session,
    *,
    tenant_id: UUID,
    email: str | None,
    phone: str | None,
) -> None:
    """Serialize duplicate checks for identical contacts on PostgreSQL.

    SQLite, used only by the isolated test suite, has no advisory locks. The
    locks are transaction-scoped and are released on commit or rollback.
    """

    if session.get_bind().dialect.name != "postgresql":
        return

    keys: list[int] = []
    if phone is not None:
        keys.append(_advisory_key("phone", phone, tenant_id=tenant_id))
    if email is not None:
        keys.append(_advisory_key("email", email, tenant_id=tenant_id))
    for key in sorted(set(keys)):
        session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": key},
        )


def _raise_if_duplicate(
    session: Session,
    *,
    tenant_id: UUID,
    email: str | None,
    phone: str | None,
    exclude_lead_id: UUID | None = None,
) -> None:
    matches, matching_fields = repository.find_duplicate_leads(
        session,
        tenant_id=tenant_id,
        email=email,
        phone=phone,
        exclude_lead_id=exclude_lead_id,
    )
    if matches:
        raise DuplicateLeadError(
            matching_lead_ids=[match.id for match in matches],
            matching_fields=matching_fields,
        )


def _lead_response(lead: Lead) -> LeadResponse:
    return LeadResponse.model_validate(lead)


def _assignment_response(assignment: LeadAssignment) -> LeadAssignmentResponse:
    return LeadAssignmentResponse.model_validate(assignment)


def _duplicate_summary(
    *,
    matching_lead_ids: list[UUID],
    matching_fields: list[str],
) -> str:
    if not matching_lead_ids:
        return "No existing lead matches the supplied contact information."
    count = len(matching_lead_ids)
    field_text = " and ".join(matching_fields) or "contact"
    noun = "lead" if count == 1 else "leads"
    verb = "matches" if count == 1 else "match"
    return f"{count} existing {noun} {verb} the supplied {field_text}."


def _get_visible_lead(
    session: Session,
    *,
    actor: User,
    lead_id: UUID,
    for_update: bool = False,
) -> Lead:
    """Return a lead only when the caller may manage it.

    Administrators see every lead. Sales executives see only leads actively
    assigned to them on an active project. Hidden records return 404 so their
    existence is not disclosed.
    """

    _require_lead_manager(actor)
    lead = repository.get_lead_by_id(
        session,
        lead_id,
        tenant_id=actor.tenant_id,
        for_update=for_update,
    )
    if lead is None:
        raise LeadNotFoundError()

    if _is_admin(actor):
        return lead

    if lead.project.status != ProjectStatus.ACTIVE.value:
        raise LeadNotFoundError()
    if (
        lead.current_assignment is None
        or lead.current_assignment.executive_id != actor.id
    ):
        raise LeadNotFoundError()
    return lead


_local_process_contact_lock = Lock()


def create_lead(
    session: Session,
    *,
    actor: User | None = None,
    payload: LeadCreateRequest,
) -> LeadResponse:
    """Create a public/staff lead after project, budget, and duplicate checks.

    When no actor is supplied (public website intake) the owning tenant is
    derived from the active project identified by ``payload.project_id``.
    """

    if actor is not None:
        project = _project_is_active(
            session, payload.project_id, tenant_id=actor.tenant_id
        )
        tenant_id = actor.tenant_id
    else:
        project = _resolve_active_project_any_tenant(session, payload.project_id)
        tenant_id = project.tenant_id

    email_value = str(payload.email) if payload.email is not None else None
    phone_value = payload.phone

    _lock_contact_keys(
        session,
        tenant_id=tenant_id,
        email=email_value,
        phone=phone_value,
    )
    with _local_process_contact_lock:
        from app.modules.billing.service import ensure_within_plan_limits

        ensure_within_plan_limits(session, tenant_id=tenant_id, kind="leads")
        _raise_if_duplicate(
            session,
            tenant_id=tenant_id,
            email=email_value,
            phone=phone_value,
        )

        lead = Lead(
            tenant_id=tenant_id,
            full_name=payload.full_name,
            email=email_value,
            phone=phone_value,
            project_id=payload.project_id,
            source=payload.source.value,
            status=LeadStatus.NEW.value,
            budget_min=payload.budget_min,
            budget_max=payload.budget_max,
            preferred_configuration=payload.preferred_configuration,
            consent_to_contact=payload.consent_to_contact,
            opted_out=not payload.consent_to_contact,
        )
        session.add(lead)
        session.flush()
        try:
            from app.modules.messaging.engine import emit_event

            emit_event(
                session,
                tenant_id=tenant_id,
                event="lead.created",
                context={
                    "entity_type": "lead",
                    "entity_id": lead.id,
                    "first_name": lead.full_name.split(" ", 1)[0],
                    "full_name": lead.full_name,
                    "project_name": project.name,
                    "phone": lead.phone,
                    "email": lead.email,
                    "to_address": lead.phone or lead.email,
                    "source": lead.source,
                },
            )
        except Exception as exc:
            logger.warning("Could not emit lead.created messaging event: %s", exc)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            # The advisory lock normally prevents this race. If a database
            # constraint still fails, surface the duplicate rather than a 500.
            _raise_if_duplicate(
                session,
                tenant_id=tenant_id,
                email=email_value,
                phone=phone_value,
            )
            raise

        session.refresh(lead)
        return _lead_response(lead)


def check_duplicates(
    session: Session,
    *,
    actor: User,
    email: str | None,
    phone: str | None,
) -> DuplicateCheckResponse:
    """Return safe duplicate references for administrators only."""

    _require_admin(actor)
    matches, matching_fields = repository.find_duplicate_leads(
        session,
        tenant_id=actor.tenant_id,
        email=email,
        phone=phone,
    )
    matching_ids = [match.id for match in matches]
    return DuplicateCheckResponse(
        duplicate=bool(matching_ids),
        matching_lead_ids=matching_ids,
        matching_fields=matching_fields,  # type: ignore[arg-type]
        summary=_duplicate_summary(
            matching_lead_ids=matching_ids,
            matching_fields=matching_fields,
        ),
    )


def list_leads_for_buyer(
    session: Session,
    *,
    actor: User,
) -> list[LeadResponse]:
    """Return leads linked to the current buyer's email address.

    Buyers may only discover their own leads, matched by the email on their
    account. This is used to surface DPDP opt-out for leads that have no
    conversation history yet.
    """

    if actor.email is None:
        return []
    leads = repository.find_leads_by_email(
        session,
        tenant_id=actor.tenant_id,
        email=actor.email.lower(),
    )
    return [_lead_response(lead) for lead in leads]


def list_leads(
    session: Session,
    *,
    actor: User,
    page: int,
    page_size: int,
    search: str | None = None,
    project_id: UUID | None = None,
    source: LeadSource | None = None,
    status: LeadStatus | None = None,
    assigned_executive_id: UUID | None = None,
    newest_first: bool = True,
    opted_out: bool | None = None,
) -> LeadListResponse:
    """Return a bounded page of leads visible to the caller."""

    _require_lead_manager(actor)
    search_value = search.strip() if search and search.strip() else None

    # The opt-out register is an admin capability, not row scoping: a custom
    # role with leads.manage may read it even when the base role is not ADMIN.
    from app.modules.auth.dependencies import has_permission
    from app.modules.users.permissions import LEADS_MANAGE

    can_manage = _is_admin(actor) or has_permission(actor, LEADS_MANAGE)
    if can_manage:
        active_project_only = False
        executive_filter = assigned_executive_id
    else:
        active_project_only = True
        # Sales executives cannot use the filter to inspect another
        # executive's leads; the filter is clamped to their own identity.
        executive_filter = actor.id
        # Sales executives may not inspect the admin opt-out register.
        if opted_out:
            raise InsufficientPermissionsError()

    total = repository.count_leads(
        session,
        tenant_id=actor.tenant_id,
        search=search_value,
        project_id=project_id,
        source=source,
        status=status,
        assigned_executive_id=executive_filter,
        active_project_only=active_project_only,
        opted_out=opted_out,
    )
    items = repository.list_leads(
        session,
        tenant_id=actor.tenant_id,
        offset=(page - 1) * page_size,
        limit=page_size,
        search=search_value,
        project_id=project_id,
        source=source,
        status=status,
        assigned_executive_id=executive_filter,
        active_project_only=active_project_only,
        newest_first=newest_first,
        opted_out=opted_out,
    )
    return LeadListResponse(
        items=[_lead_response(lead) for lead in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )


def list_opted_out_leads(
    session: Session,
    *,
    actor: User,
    page: int,
    page_size: int,
) -> LeadListResponse:
    """Return the tenant's opted-out lead register (admin only)."""

    _require_admin(actor)
    return list_leads(
        session,
        actor=actor,
        page=page,
        page_size=page_size,
        opted_out=True,
    )


def get_lead(
    session: Session,
    *,
    actor: User,
    lead_id: UUID,
) -> LeadResponse:
    """Return one lead when the caller is authorized to manage it."""

    lead = _get_visible_lead(session, actor=actor, lead_id=lead_id)
    return _lead_response(lead)


def update_lead(
    session: Session,
    *,
    actor: User,
    lead_id: UUID,
    payload: LeadUpdateRequest,
) -> LeadResponse:
    """Update permitted fields while preserving omitted values."""

    lead = _get_visible_lead(
        session,
        actor=actor,
        lead_id=lead_id,
        for_update=True,
    )
    fields = payload.model_dump(exclude_unset=True)

    if not _is_admin(actor):
        denied = set(fields) & _SALES_ADMIN_ONLY_FIELDS
        if denied:
            raise LeadFieldAccessDeniedError(sorted(denied))

    budget_min = fields.get("budget_min", lead.budget_min)
    budget_max = fields.get("budget_max", lead.budget_max)
    if (
        budget_min is not None
        and budget_max is not None
        and budget_min > budget_max
    ):
        raise InvalidBudgetRangeError()

    new_email = fields.get("email", lead.email)
    new_phone = fields.get("phone", lead.phone)
    if new_email is None and new_phone is None:
        raise ValueError(
            "A lead must retain at least one contact method (email or phone)."
        )
    email_value = str(new_email) if new_email is not None else None

    if new_email != lead.email or new_phone != lead.phone:
        _lock_contact_keys(
            session,
            tenant_id=actor.tenant_id,
            email=email_value,
            phone=new_phone,
        )
        _raise_if_duplicate(
            session,
            tenant_id=actor.tenant_id,
            email=email_value,
            phone=new_phone,
            exclude_lead_id=lead.id,
        )

    if "project_id" in fields:
        _project_is_active(session, fields["project_id"], tenant_id=actor.tenant_id)

    changed_fields = {
        name: value
        for name, value in fields.items()
        if getattr(lead, name) != value
    }
    if not changed_fields:
        return _lead_response(lead)

    for name, value in changed_fields.items():
        setattr(lead, name, value)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if changed_fields.keys() & {"email", "phone"}:
            _raise_if_duplicate(
                session,
                tenant_id=actor.tenant_id,
                email=email_value,
                phone=new_phone,
                exclude_lead_id=lead_id,
            )
        raise

    session.refresh(lead)
    return _lead_response(lead)


def update_lead_status(
    session: Session,
    *,
    actor: User,
    lead_id: UUID,
    payload: LeadStatusUpdateRequest,
) -> LeadResponse:
    """Move a lead through the explicitly supported lifecycle graph."""

    lead = _get_visible_lead(
        session,
        actor=actor,
        lead_id=lead_id,
        for_update=True,
    )
    current = LeadStatus(lead.status)
    requested = payload.status

    if current == requested:
        return _lead_response(lead)

    if requested not in _ALLOWED_STATUS_TRANSITIONS.get(current, frozenset()):
        raise InvalidLeadStatusTransitionError(current, requested)

    if (
        requested in _CONTACT_REQUIRING_STATUSES
        and not lead.consent_to_contact
    ):
        raise LeadConsentRequiredError(requested.value.lower().replace("_", " "))

    if lead.opted_out and requested in _CONTACT_REQUIRING_STATUSES:
        raise LeadConsentRequiredError(requested.value.lower().replace("_", " "))

    lead.status = requested.value
    session.flush()
    try:
        from app.modules.messaging.engine import emit_event

        emit_event(
            session,
            tenant_id=actor.tenant_id,
            event="lead.status_changed",
            context={
                "entity_type": "lead",
                "entity_id": lead.id,
                "first_name": lead.full_name.split(" ", 1)[0],
                "full_name": lead.full_name,
                "project_name": lead.project.name if lead.project else None,
                "phone": lead.phone,
                "email": lead.email,
                "to_address": lead.phone or lead.email,
                "status": lead.status,
            },
        )
    except Exception as exc:
        logger.warning("Could not emit lead.status_changed messaging event: %s", exc)
    session.commit()
    session.refresh(lead)
    return _lead_response(lead)


def opt_out_lead(
    session: Session,
    *,
    actor: User,
    lead_id: UUID,
    payload: LeadOptOutRequest,
) -> LeadResponse:
    """Withdraw contact consent for a lead (DPDP opt-out).

    Any authenticated caller may opt out their own lead. Sales executives and
    admins may opt out any lead they can see. Once opted out, no further
    contact (notifications, reminders, follow-ups, booking confirmations) may
    be initiated to the buyer for this lead.
    """

    lead = repository.get_lead_by_id(
        session,
        lead_id,
        tenant_id=actor.tenant_id,
    )
    if lead is None:
        raise LeadNotFoundError()

    _require_lead_manager_or_buyer(actor, lead)

    if lead.opted_out:
        return _lead_response(lead)

    now = utcnow()
    lead.opted_out = True
    lead.opted_out_at = now
    lead.opted_out_reason = payload.reason
    lead.consent_to_contact = False
    lead.updated_at = now

    try:
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(lead)
    return _lead_response(lead)


def _require_lead_manager_or_buyer(actor: User, lead: Lead) -> None:
    """Allow admins, sales executives (for assigned leads), or the buyer
    (matched by email) to opt out a lead."""

    if actor.role.name in (RoleName.ADMIN.value, RoleName.SALES_EXECUTIVE.value):
        _require_lead_manager(actor)
        return

    # Buyers may opt out a lead whose email matches their own.
    if actor.email and lead.email and actor.email.lower() == lead.email.lower():
        return

    raise LeadNotFoundError()


def assign_lead(
    session: Session,
    *,
    actor: User,
    lead_id: UUID,
    payload: LeadAssignRequest,
) -> LeadAssignmentResponse:
    """Assign or reassign a lead, preserving the previous assignment segment."""

    _require_admin(actor)
    lead = repository.get_lead_by_id(
        session,
        lead_id,
        tenant_id=actor.tenant_id,
        for_update=True,
    )
    if lead is None:
        raise LeadNotFoundError()
    if not lead.consent_to_contact:
        raise LeadConsentRequiredError("lead assignment")

    if lead.opted_out:
        raise LeadConsentRequiredError("lead assignment")

    executive = users_repository.get_user_by_id(
        session, payload.executive_id, tenant_id=actor.tenant_id
    )
    if (
        executive is None
        or not executive.is_active
        or executive.role.name != RoleName.SALES_EXECUTIVE.value
    ):
        raise InvalidLeadExecutiveError()

    current = repository.get_active_assignment(
        session,
        tenant_id=actor.tenant_id,
        lead_id=lead.id,
        for_update=True,
    )
    if current is not None and current.executive_id == executive.id:
        return _assignment_response(current)

    now = utcnow()
    if current is not None:
        # Flush the closing update before inserting the replacement. The
        # partial unique index permits only one active row, and SQLAlchemy's
        # default unit-of-work order emits inserts before updates.
        current.unassigned_at = now
        session.flush()

    assignment = LeadAssignment(
        tenant_id=actor.tenant_id,
        lead_id=lead.id,
        executive_id=executive.id,
        assigned_by=actor.id,
        assigned_at=now,
    )
    session.add(assignment)
    lead.updated_at = now

    try:
        from app.modules.notifications.service import notify_lead_assigned

        notify_lead_assigned(session, lead=lead, executive=executive)
    except Exception as exc:
        logger.warning("Could not dispatch lead assignment notification: %s", exc)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise LeadAssignmentConflictError()

    session.refresh(assignment)
    return _assignment_response(assignment)


def list_lead_assignments(
    session: Session,
    *,
    actor: User,
    lead_id: UUID,
    page: int,
    page_size: int,
) -> LeadAssignmentListResponse:
    """Return assignment history to admins or the currently assigned executive."""

    _get_visible_lead(session, actor=actor, lead_id=lead_id)
    total = repository.count_assignments(
        session, tenant_id=actor.tenant_id, lead_id=lead_id
    )
    items = repository.list_assignments(
        session,
        tenant_id=actor.tenant_id,
        lead_id=lead_id,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return LeadAssignmentListResponse(
        items=[_assignment_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )
