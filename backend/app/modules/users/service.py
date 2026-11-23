"""User-management and role-seeding business logic."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.users import repository
from app.modules.users.exceptions import (
    CannotChangeOwnRoleError,
    CannotDeactivateSelfError,
    InsufficientPermissionsError,
    RoleNotFoundError,
    UserAccessDeniedError,
    UserNotFoundError,
)
from app.modules.users.models import Role, RoleName, User
from app.modules.users.schemas import (
    UserCreateRequest,
    UserListResponse,
    UserMetricsResponse,
    UserUpdateRequest,
)

_ROLE_DESCRIPTIONS: dict[RoleName, str] = {
    RoleName.BUYER: "Buyer account",
    RoleName.SALES_EXECUTIVE: "Sales executive account",
    RoleName.MANAGER: "Sales/inventory manager",
    RoleName.ADMIN: "Administrator account",
}


def seed_roles(session: Session) -> list[RoleName]:
    """Create any missing built-in roles and return the roles created.

    Re-running the function is safe: existing roles are left untouched and a
    concurrent insert conflict is treated as another process having completed
    the same idempotent seed.
    """

    existing_names = {role.name for role in repository.list_roles(session)}
    created: list[RoleName] = []
    for role_name in RoleName:
        if role_name.value not in existing_names:
            session.add(
                Role(
                    name=role_name.value,
                    description=_ROLE_DESCRIPTIONS[role_name],
                )
            )
            created.append(role_name)

    if created:
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return []

    return created


def _is_admin(user: User) -> bool:
    return user.custom_role_id is None and user.role.name == RoleName.ADMIN.value


def _require_admin(user: User) -> None:
    if not _is_admin(user):
        raise InsufficientPermissionsError()


def _get_existing_user(
    session: Session, user_id: UUID, *, tenant_id: UUID
) -> User:
    user = repository.get_user_by_id(session, user_id, tenant_id=tenant_id)
    if user is None:
        raise UserNotFoundError()
    return user


def get_accessible_user(
    session: Session,
    *,
    actor: User,
    user_id: UUID,
) -> User:
    """Return a user only when the actor is an admin or the user themself."""

    user = _get_existing_user(session, user_id, tenant_id=actor.tenant_id)
    if not _is_admin(actor) and actor.id != user.id:
        raise UserAccessDeniedError()
    return user


def list_users(
    session: Session,
    *,
    actor: User,
    page: int,
    page_size: int,
    search: str | None = None,
    role_name: RoleName | str | None = None,
    is_active: bool | None = None,
) -> UserListResponse:
    """Return a paginated user listing for administrators."""

    _require_admin(actor)
    total = repository.count_users(
        session,
        tenant_id=actor.tenant_id,
        search=search,
        role_name=role_name,
        is_active=is_active,
    )
    items = repository.list_users(
        session,
        tenant_id=actor.tenant_id,
        offset=(page - 1) * page_size,
        limit=page_size,
        search=search,
        role_name=role_name,
        is_active=is_active,
    )
    pages = (total + page_size - 1) // page_size if total else 0
    return UserListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


def get_user_metrics_summary(
    session: Session,
    *,
    actor: User,
) -> UserMetricsResponse:
    """Compute aggregate user metrics for administrators."""

    _require_admin(actor)
    metrics = repository.get_user_metrics(session, tenant_id=actor.tenant_id)
    return UserMetricsResponse(**metrics)


def create_user_by_admin(
    session: Session,
    *,
    actor: User,
    payload: UserCreateRequest,
) -> User:
    """Provision a user account with an explicit role. Requires the ADMIN role."""

    _require_admin(actor)
    from app.modules.auth.service import create_user_with_role
    from app.modules.billing.service import ensure_within_plan_limits

    ensure_within_plan_limits(session, tenant_id=actor.tenant_id, kind="users")

    user = create_user_with_role(
        session,
        full_name=payload.full_name,
        email=str(payload.email),
        password=payload.password,
        phone=payload.phone,
        role_name=payload.role,
        is_active=payload.is_active,
        tenant_id=actor.tenant_id,
    )
    if payload.custom_role_id is not None:
        from app.modules.users import role_repository

        custom_role = role_repository.get_custom_role(
            session, payload.custom_role_id, tenant_id=actor.tenant_id
        )
        if custom_role is None:
            session.delete(user)
            session.commit()
            raise RoleNotFoundError()
        user.custom_role_id = custom_role.id
        user.role = repository.get_role_by_name(session, RoleName.SALES_EXECUTIVE)
        session.commit()
        session.refresh(user)
    return user


def update_user(
    session: Session,
    *,
    actor: User,
    user_id: UUID,
    payload: UserUpdateRequest,
) -> User:
    """Update a user's permitted profile fields and, for admins, their role."""

    user = get_accessible_user(session, actor=actor, user_id=user_id)
    fields = payload.model_dump(exclude_unset=True)

    if "role" in fields or "custom_role_id" in fields:
        if actor.id == user.id:
            raise CannotChangeOwnRoleError()
        if not _is_admin(actor):
            raise InsufficientPermissionsError()

        if "custom_role_id" in fields:
            from app.modules.users import role_repository

            custom_role = role_repository.get_custom_role(
                session,
                fields.pop("custom_role_id"),
                tenant_id=actor.tenant_id,
            )
            if custom_role is None:
                raise RoleNotFoundError()
            user.custom_role_id = custom_role.id
            user.role = repository.get_role_by_name(session, RoleName.SALES_EXECUTIVE)
        else:
            requested_role = fields.pop("role")
            role = repository.get_role_by_name(session, requested_role)
            if role is None:
                raise RoleNotFoundError()
            user.role = role
            user.custom_role_id = None
        user.security_version += 1

    if "full_name" in fields:
        user.full_name = fields["full_name"]

    if "phone" in fields:
        user.phone = fields["phone"]

    session.commit()
    session.refresh(user)
    return user


def update_user_status(
    session: Session,
    *,
    actor: User,
    user_id: UUID,
    is_active: bool,
) -> User:
    """Activate or deactivate a user. Administrator access is required."""

    _require_admin(actor)
    user = _get_existing_user(session, user_id, tenant_id=actor.tenant_id)

    if actor.id == user.id and not is_active:
        raise CannotDeactivateSelfError()

    user.is_active = is_active
    session.commit()
    session.refresh(user)
    return user
