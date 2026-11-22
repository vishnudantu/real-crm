"""Customer + opportunity graph HTTP endpoints (prefix /customers)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import CurrentUser, require_roles
from app.modules.customers import service
from app.modules.customers.schemas import (
    ContactCreateRequest,
    ContactCreateResponse,
    ContactDetailResponse,
    ContactListResponse,
    ContactMethodResponse,
    ContactResolvePreviewResponse,
    ContactResponse,
    ContactUpdateRequest,
    Customer360Response,
    DuplicateSuggestionsResponse,
    MergeListResponse,
    MergeRequest,
    MergeResponse,
    OpportunityCreateRequest,
    OpportunityListResponse,
    OpportunityResponse,
    OpportunityUpdateRequest,
    ContactSearchRequest,
)
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/customers", tags=["customers"])
opportunities_router = APIRouter(prefix="/opportunities", tags=["opportunities"])

ManagerUser = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE)),
]


@router.post(
    "/search",
    response_model=ContactResolvePreviewResponse,
    summary="Resolve a contact preview (no writes)",
)
def search_contact_endpoint(
    payload: ContactSearchRequest,
    current_user: ManagerUser,
    db: Annotated[Session, Depends(get_db)],
) -> ContactResolvePreviewResponse:
    contact, method, created = service.resolve_contact(
        db,
        tenant_id=current_user.tenant_id,
        email=str(payload.email) if payload.email else None,
        phone=payload.phone,
        display_name=payload.display_name,
        create_if_missing=False,
    )
    if contact is None:
        return ContactResolvePreviewResponse(
            exists=False,
            would_create=True,
            normalized_email=str(payload.email) if payload.email else None,
            normalized_phone=payload.phone,
        )
    return ContactResolvePreviewResponse(
        exists=True,
        would_create=False,
        contact=ContactResponse.model_validate(contact),
        matched_method=method,
        normalized_email=str(payload.email) if payload.email else None,
        normalized_phone=payload.phone,
    )


@router.get("", response_model=ContactListResponse, summary="List contacts")
def list_contacts_endpoint(
    current_user: ManagerUser,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: str | None = None,
) -> ContactListResponse:
    return service.list_contacts(
        db, actor=current_user, page=page, page_size=page_size, search=search
    )


@router.post(
    "/contacts",
    response_model=ContactCreateResponse,
    summary="Create a contact from the console (idempotent by identity)",
)
def create_contact_endpoint(
    payload: ContactCreateRequest,
    current_user: ManagerUser,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> ContactCreateResponse:
    """Create-or-resolve a contact.

    Status code is set manually because it depends on resolution:
    **201** when a new contact was created (``created=true``), **200** when
    the normalized email/phone already resolved to an existing contact
    (``created=false``) — a repeat submission is idempotent, never a 409.
    Response: ``{contact, method, created}``.
    """
    contact, method, created = service.create_contact(
        db,
        actor=current_user,
        display_name=payload.display_name,
        email=str(payload.email) if payload.email else None,
        phone=payload.phone,
        primary_language=payload.primary_language,
        notes=payload.notes,
    )
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return ContactCreateResponse(
        contact=ContactDetailResponse.model_validate(contact),
        method=ContactMethodResponse.model_validate(method) if method else None,
        created=created,
    )


@router.patch(
    "/contacts/{contact_id}",
    response_model=ContactResponse,
    summary="Update editable contact profile fields",
)
def update_contact_endpoint(
    contact_id: UUID,
    payload: ContactUpdateRequest,
    current_user: ManagerUser,
    db: Annotated[Session, Depends(get_db)],
) -> ContactResponse:
    """Editable: display_name / primary_language / notes only.

    status and merged_into_id change only through the merge endpoints and are
    rejected here (400 or 422 via extra="forbid"). An empty PATCH body is a
    400. Tenant visibility is enforced by ``_get_visible_contact``.
    """
    fields = payload.model_dump(exclude_unset=True)
    contact = service.update_contact(
        db, actor=current_user, contact_id=contact_id, fields=fields
    )
    return ContactResponse.model_validate(contact)


@router.get(
    "/merges",
    response_model=MergeListResponse,
    summary="List merge history (newest first, tenant scoped)",
)
def list_merges_endpoint(
    current_user: ManagerUser,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MergeListResponse:
    """Historical merges for the revert UI.

    Response: ``{items: [MergeResponse...], total, limit, offset}`` with each
    item carrying ``{id, survivor_id, merged_id, actor_user_id, reason,
    evidence, reverted_at, created_at}``.
    """
    return service.list_merges(db, actor=current_user, limit=limit, offset=offset)


@router.get(
    "/{contact_id}",
    response_model=Customer360Response,
    summary="Get a contact 360 view",
)
def get_contact_endpoint(
    contact_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> Customer360Response:
    # Visibility check (buyer own-contact / manager) then aggregate.
    service._get_visible_contact(db, actor=current_user, contact_id=contact_id)
    return service.customer_360(
        db, tenant_id=current_user.tenant_id, contact_id=contact_id
    )


@router.get(
    "/{contact_id}/timeline",
    response_model=Customer360Response,
    summary="Get a contact's aggregated timeline",
)
def get_contact_timeline_endpoint(
    contact_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> Customer360Response:
    service._get_visible_contact(db, actor=current_user, contact_id=contact_id)
    return service.customer_360(
        db, tenant_id=current_user.tenant_id, contact_id=contact_id
    )


@router.get(
    "/{contact_id}/duplicates",
    response_model=DuplicateSuggestionsResponse,
    summary="Suggest duplicate contacts",
)
def get_duplicates_endpoint(
    contact_id: UUID,
    current_user: ManagerUser,
    db: Annotated[Session, Depends(get_db)],
) -> DuplicateSuggestionsResponse:
    return service.suggest_duplicates(
        db, tenant_id=current_user.tenant_id, contact_id=contact_id
    )


@router.post(
    "/{contact_id}/merge",
    response_model=MergeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Merge another contact into this one (path id = survivor)",
)
def merge_contact_endpoint(
    contact_id: UUID,
    payload: MergeRequest,
    current_user: ManagerUser,
    db: Annotated[Session, Depends(get_db)],
) -> MergeResponse:
    merge = service.merge_contacts(
        db,
        actor=current_user,
        survivor_id=contact_id,
        merged_id=payload.merged_id,
        reason=payload.reason,
    )
    return service.merge_response(merge)


@router.post(
    "/merges/{merge_id}/revert",
    response_model=MergeResponse,
    summary="Revert a contact merge exactly",
)
def revert_merge_endpoint(
    merge_id: UUID,
    current_user: ManagerUser,
    db: Annotated[Session, Depends(get_db)],
) -> MergeResponse:
    merge = service.unmerge_contacts(db, actor=current_user, merge_id=merge_id)
    return service.merge_response(merge)


@router.post(
    "/{contact_id}/opportunities",
    response_model=OpportunityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Open an opportunity for a contact",
)
def open_opportunity_endpoint(
    contact_id: UUID,
    payload: OpportunityCreateRequest,
    current_user: ManagerUser,
    db: Annotated[Session, Depends(get_db)],
) -> OpportunityResponse:
    opp = service.open_opportunity(
        db,
        actor=current_user,
        contact_id=contact_id,
        project_id=payload.project_id,
        from_lead_id=payload.from_lead_id,
        owner_user_id=payload.owner_user_id,
        budget_min=payload.budget_min,
        budget_max=payload.budget_max,
        preferred_configuration=payload.preferred_configuration,
        source=payload.source,
        value_paise=payload.value_paise,
    )
    return OpportunityResponse.model_validate(opp)


@opportunities_router.get(
    "", response_model=OpportunityListResponse, summary="List opportunities"
)
def list_opportunities_endpoint(
    current_user: ManagerUser,
    db: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OpportunityListResponse:
    return service.list_opportunities(
        db, actor=current_user, page=page, page_size=page_size
    )


@opportunities_router.patch(
    "/{opportunity_id}",
    response_model=OpportunityResponse,
    summary="Update an opportunity (stage transitions validated)",
)
def update_opportunity_endpoint(
    opportunity_id: UUID,
    payload: OpportunityUpdateRequest,
    current_user: ManagerUser,
    db: Annotated[Session, Depends(get_db)],
) -> OpportunityResponse:
    fields = payload.model_dump(exclude_unset=True)
    opp = service.update_opportunity(
        db, actor=current_user, opportunity_id=opportunity_id, fields=fields
    )
    return OpportunityResponse.model_validate(opp)
