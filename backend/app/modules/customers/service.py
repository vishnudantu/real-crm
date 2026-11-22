"""Customer + opportunity graph service (PF-008/PF-009)."""

from __future__ import annotations

import re
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.customers.exceptions import (
    ContactNotFoundError,
    CustomerAccessDeniedError,
    InvalidStageTransitionError,
    MergeError,
    MergeNotFoundError,
    OpportunityConflictError,
    OpportunityNotFoundError,
)
from app.modules.customers.models import (
    Contact,
    ContactMerge,
    ContactMethod,
    ContactMethodKind,
    ContactStatus,
    Opportunity,
    OpportunityStage,
    VerificationState,
    utcnow,
)
from app.modules.customers.schemas import (
    ContactListResponse,
    ContactResponse,
    Customer360Response,
    DuplicateCandidate,
    DuplicateSuggestionsResponse,
    MergeEvidenceField,
    MergeResponse,
    OpportunityListResponse,
    OpportunityResponse,
)
from app.modules.customers.timeline import build_customer_360
from app.modules.leads.models import Lead
from app.modules.leads.schemas import normalize_email, normalize_phone
from app.modules.projects.models import Project
from app.modules.users.models import RoleName, User

# Explicit allowed stage transitions. NEW..NEGOTIATING are the active pipeline;
# BOOKED marks a unit booked; WON is terminal success; LOST/LOST_DORMANT are
# terminal loss (LOST_DORMANT may be re-opened to CONTACTED for nurture).
_ALLOWED_STAGE_TRANSITIONS: dict[OpportunityStage, frozenset[OpportunityStage]] = {
    OpportunityStage.NEW: frozenset(
        {OpportunityStage.CONTACTED, OpportunityStage.QUALIFIED, OpportunityStage.LOST}
    ),
    OpportunityStage.CONTACTED: frozenset(
        {
            OpportunityStage.QUALIFIED,
            OpportunityStage.VISIT_SCHEDULED,
            OpportunityStage.LOST,
        }
    ),
    OpportunityStage.QUALIFIED: frozenset(
        {OpportunityStage.VISIT_SCHEDULED, OpportunityStage.NEGOTIATING, OpportunityStage.LOST}
    ),
    OpportunityStage.VISIT_SCHEDULED: frozenset(
        {OpportunityStage.VISITED, OpportunityStage.LOST}
    ),
    OpportunityStage.VISITED: frozenset(
        {OpportunityStage.NEGOTIATING, OpportunityStage.BOOKED, OpportunityStage.LOST}
    ),
    OpportunityStage.NEGOTIATING: frozenset(
        {OpportunityStage.BOOKED, OpportunityStage.WON, OpportunityStage.LOST}
    ),
    OpportunityStage.BOOKED: frozenset({OpportunityStage.WON, OpportunityStage.LOST}),
    OpportunityStage.WON: frozenset(),
    OpportunityStage.LOST: frozenset({OpportunityStage.LOST_DORMANT}),
    OpportunityStage.LOST_DORMANT: frozenset({OpportunityStage.CONTACTED}),
}

_ACTIVE_OPPORTUNITY_STAGES = frozenset(
    {
        OpportunityStage.NEW.value,
        OpportunityStage.CONTACTED.value,
        OpportunityStage.QUALIFIED.value,
        OpportunityStage.VISIT_SCHEDULED.value,
        OpportunityStage.VISITED.value,
        OpportunityStage.NEGOTIATING.value,
        OpportunityStage.BOOKED.value,
    }
)


def _is_admin(actor: User) -> bool:
    return actor.role.name == RoleName.ADMIN.value


def _is_manager(actor: User) -> bool:
    return actor.role.name in (RoleName.ADMIN.value, RoleName.SALES_EXECUTIVE.value)


def _pages(total: int, page_size: int) -> int:
    return (total + page_size - 1) // page_size if total else 0


def _normalize_method_value(kind: ContactMethodKind, value: str) -> str:
    """Normalize a contact method value for storage/matching."""
    if kind in (ContactMethodKind.PHONE, ContactMethodKind.WHATSAPP_ID):
        return normalize_phone(value)
    normalized = normalize_email(value)
    assert normalized is not None
    return str(normalized)


def _canonical_key_for(methods: list[ContactMethod]) -> str:
    """Pick the lowest verified method value, else a fresh uuid key."""
    verified = [
        m for m in methods if m.verification_state == VerificationState.VERIFIED.value
    ]
    if not verified:
        return f"uuid:{uuid4()}"
    lowest = min(verified, key=lambda m: (m.kind.lower(), m.normalized_value))
    return f"{lowest.kind.lower()}:{lowest.normalized_value}"


def _own_contact_check(session: Session, *, actor: User, contact: Contact) -> bool:
    """A buyer may access only the contact whose primary EMAIL method matches
    their account email (documented minimal own-contact rule)."""
    if actor.role.name != RoleName.BUYER.value:
        return False
    if not actor.email:
        return False
    email = actor.email.lower()
    for method in contact.methods:
        if (
            method.kind == ContactMethodKind.EMAIL.value
            and method.is_primary
            and method.normalized_value == email
        ):
            return True
    return False


def _get_visible_contact(
    session: Session, *, actor: User, contact_id: UUID
) -> Contact:
    """Tenant-scoped fetch; cross-tenant returns 404. Buyers limited to own."""
    contact = session.scalar(
        select(Contact)
        .options(selectinload(Contact.methods))
        .where(Contact.id == contact_id, Contact.tenant_id == actor.tenant_id)
    )
    if contact is None:
        raise ContactNotFoundError()
    if _is_manager(actor):
        return contact
    if _own_contact_check(session, actor=actor, contact=contact):
        return contact
    raise CustomerAccessDeniedError()


# --------------------------------------------------------------------------- #
# resolve_contact / suggest_duplicates
# --------------------------------------------------------------------------- #


def resolve_contact(
    session: Session,
    *,
    tenant_id: UUID,
    email: str | None = None,
    phone: str | None = None,
    display_name: str | None = None,
    provenance: dict | None = None,
    create_if_missing: bool = True,
) -> tuple[Contact | None, ContactMethod | None, bool]:
    """Deterministic identity resolution: exact normalized match within tenant.

    Returns ``(contact, matched_method, created)``. When no match and
    ``create_if_missing`` is False, returns ``(None, None, False)``.
    """
    candidates: list[tuple[ContactMethodKind, str]] = []
    if email:
        candidates.append(
            (ContactMethodKind.EMAIL, str(normalize_email(email)))
        )
    if phone:
        candidates.append((ContactMethodKind.PHONE, normalize_phone(phone)))

    for kind, normalized in candidates:
        method = session.scalar(
            select(ContactMethod).where(
                ContactMethod.tenant_id == tenant_id,
                ContactMethod.kind == kind.value,
                ContactMethod.normalized_value == normalized,
            )
        )
        if method is not None:
            contact = session.get(Contact, method.contact_id)
            assert contact is not None
            method.last_seen_at = utcnow()
            session.flush()
            return contact, method, False

    if not create_if_missing:
        return None, None, False

    if not candidates:
        raise ValueError("At least one of email or phone is required.")

    # Create contact + first method atomically.
    primary_kind, primary_normalized = candidates[0]
    contact = Contact(
        tenant_id=tenant_id,
        canonical_key=f"uuid:{uuid4()}",
        display_name=display_name or primary_normalized,
        status=ContactStatus.ACTIVE.value,
    )
    session.add(contact)
    session.flush()
    now = utcnow()
    method = ContactMethod(
        tenant_id=tenant_id,
        contact_id=contact.id,
        kind=primary_kind.value,
        value=email if primary_kind == ContactMethodKind.EMAIL else phone,
        normalized_value=primary_normalized,
        verification_state=VerificationState.UNVERIFIED.value,
        provenance=provenance or {},
        is_primary=True,
        last_seen_at=now,
    )
    session.add(method)
    session.flush()
    # Attach any secondary provided method too (best-effort, non-primary).
    for kind, normalized in candidates[1:]:
        secondary = ContactMethod(
            tenant_id=tenant_id,
            contact_id=contact.id,
            kind=kind.value,
            value=email if kind == ContactMethodKind.EMAIL else phone,
            normalized_value=normalized,
            verification_state=VerificationState.UNVERIFIED.value,
            provenance=provenance or {},
            is_primary=False,
            last_seen_at=now,
        )
        session.add(secondary)
    session.flush()
    session.refresh(contact)
    return contact, method, True


def _last_ten_digits(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return digits[-10:] if len(digits) >= 10 else digits


def suggest_duplicates(
    session: Session, *, tenant_id: UUID, contact_id: UUID
) -> DuplicateSuggestionsResponse:
    """Suggest duplicate contacts for the given contact with match evidence.

    Rules (deterministic only):
      * EXACT — another contact shares the same normalized EMAIL value.
      * HIGH  — another contact's PHONE/WHATSAPP_ID shares the same last-10
        digits, or the same normalized digits with different stored format.
    """
    contact = session.scalar(
        select(Contact)
        .options(selectinload(Contact.methods))
        .where(Contact.id == contact_id, Contact.tenant_id == tenant_id)
    )
    if contact is None:
        raise ContactNotFoundError()

    own_methods = list(contact.methods)
    if not own_methods:
        return DuplicateSuggestionsResponse(contact_id=contact_id, candidates=[])

    # Gather all other methods in the tenant (excluding merged-away contacts).
    others = list(
        session.scalars(
            select(ContactMethod)
            .join(Contact, Contact.id == ContactMethod.contact_id)
            .where(
                ContactMethod.tenant_id == tenant_id,
                ContactMethod.contact_id != contact_id,
                Contact.status == ContactStatus.ACTIVE.value,
            )
        ).all()
    )

    own_emails = {
        m.normalized_value
        for m in own_methods
        if m.kind == ContactMethodKind.EMAIL.value
    }
    own_phone_digits = {
        m.normalized_value: _last_ten_digits(m.normalized_value)
        for m in own_methods
        if m.kind in (ContactMethodKind.PHONE.value, ContactMethodKind.WHATSAPP_ID.value)
    }

    candidates_by_contact: dict[UUID, DuplicateCandidate] = {}
    for other in others:
        confidence: str | None = None
        evidence = ""
        matched_field: MergeEvidenceField | None = None

        if (
            other.kind == ContactMethodKind.EMAIL.value
            and other.normalized_value in own_emails
        ):
            confidence = "EXACT"
            evidence = f"Identical normalized email {other.normalized_value}."
            matched_field = MergeEvidenceField(
                kind=other.kind,
                value=other.value,
                normalized_value=other.normalized_value,
            )
        elif other.kind in (
            ContactMethodKind.PHONE.value,
            ContactMethodKind.WHATSAPP_ID.value,
        ):
            other_digits = _last_ten_digits(other.normalized_value)
            for own_norm, own_last10 in own_phone_digits.items():
                if not other_digits or not own_last10:
                    continue
                if other_digits == own_last10:
                    confidence = "HIGH"
                    evidence = (
                        f"Shared last-10 digits ({other_digits}) across "
                        f"PHONE/WHATSAPP kinds (own {own_norm})."
                    )
                    matched_field = MergeEvidenceField(
                        kind=other.kind,
                        value=other.value,
                        normalized_value=other.normalized_value,
                    )
                    break

        if confidence is None or matched_field is None:
            continue

        other_contact = session.get(Contact, other.contact_id)
        if other_contact is None:
            continue

        existing = candidates_by_contact.get(other.contact_id)
        if existing is None:
            candidates_by_contact[other.contact_id] = DuplicateCandidate(
                contact_id=other.contact_id,
                display_name=other_contact.display_name,
                confidence=confidence,
                matched_fields=[matched_field],
                evidence=evidence,
            )
        else:
            # Upgrade to EXACT if any exact match; append field evidence.
            if confidence == "EXACT":
                existing.confidence = "EXACT"
            existing.matched_fields.append(matched_field)
            existing.evidence = existing.evidence + " " + evidence

    # EXACT first, then HIGH; stable by contact id for determinism.
    ranked = sorted(
        candidates_by_contact.values(),
        key=lambda c: (0 if c.confidence == "EXACT" else 1, str(c.contact_id)),
    )
    return DuplicateSuggestionsResponse(contact_id=contact_id, candidates=ranked)


# --------------------------------------------------------------------------- #
# merge / unmerge
# --------------------------------------------------------------------------- #


def merge_contacts(
    session: Session,
    *,
    actor: User,
    survivor_id: UUID,
    merged_id: UUID,
    reason: str | None = None,
) -> ContactMerge:
    """Transactional merge. Survivor absorbs merged contact's graph.

    * Methods: moved to survivor; on (tenant,kind,normalized_value) conflict
      the survivor's method wins and the loser method stays on the merged
      contact with a provenance note (so revert is exact).
    * Opportunities: repointed to survivor. If both contacts have an
      opportunity on the SAME project they are kept as separate rows
      (documented: per-project intents are independent).
    * Merged contact -> status=MERGED, merged_into_id=survivor.id.
    * ContactMerge.evidence records moved ids for exact revert.
    """
    if survivor_id == merged_id:
        raise MergeError("Cannot merge a contact into itself.")

    survivor = session.scalar(
        select(Contact)
        .options(selectinload(Contact.methods))
        .where(Contact.id == survivor_id, Contact.tenant_id == actor.tenant_id)
    )
    merged = session.scalar(
        select(Contact)
        .options(selectinload(Contact.methods))
        .where(Contact.id == merged_id, Contact.tenant_id == actor.tenant_id)
    )
    if survivor is None or merged is None:
        raise ContactNotFoundError()
    if survivor.tenant_id != merged.tenant_id:
        raise MergeError("Cannot merge contacts across tenants.")
    if merged.status == ContactStatus.MERGED.value:
        raise MergeError("Contact is already merged.")

    survivor_keys = {
        (m.kind, m.normalized_value) for m in survivor.methods
    }

    moved_method_ids: list[str] = []
    skipped_method_ids: list[str] = []

    for method in list(merged.methods):
        key = (method.kind, method.normalized_value)
        if key in survivor_keys:
            prov = dict(method.provenance or {})
            prov["merge_note"] = (
                f"Duplicate of survivor method on {survivor_id}; kept on "
                f"merged contact during merge."
            )
            method.provenance = prov
            skipped_method_ids.append(str(method.id))
        else:
            method.contact_id = survivor.id
            moved_method_ids.append(str(method.id))
            survivor_keys.add(key)

    # Repoint opportunities (keep same-project opportunities separate).
    moved_opps = list(
        session.scalars(
            select(Opportunity).where(
                Opportunity.tenant_id == actor.tenant_id,
                Opportunity.contact_id == merged.id,
            )
        ).all()
    )
    repointed_opportunity_ids: list[str] = []
    for opp in moved_opps:
        opp.contact_id = survivor.id
        repointed_opportunity_ids.append(str(opp.id))

    merged_previous_status = merged.status
    merged_previous_display_name = merged.display_name
    merged.status = ContactStatus.MERGED.value
    merged.merged_into_id = survivor.id
    merged.updated_at = utcnow()
    survivor.updated_at = utcnow()

    evidence = {
        "moved_method_ids": moved_method_ids,
        "skipped_method_ids": skipped_method_ids,
        "repointed_opportunity_ids": repointed_opportunity_ids,
        "survivor_canonical_key": survivor.canonical_key,
        "merged_canonical_key": merged.canonical_key,
        "merged_previous_status": merged_previous_status,
        "merged_previous_display_name": merged_previous_display_name,
    }

    merge = ContactMerge(
        tenant_id=actor.tenant_id,
        survivor_id=survivor.id,
        merged_id=merged.id,
        actor_user_id=actor.id,
        reason=reason,
        evidence=evidence,
    )
    session.add(merge)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise MergeError("Merge conflicted with existing contact methods.") from exc
    session.refresh(merge)
    return merge


def unmerge_contacts(
    session: Session, *, actor: User, merge_id: UUID
) -> ContactMerge:
    """Revert a merge exactly using the evidence mapping recorded at merge."""
    merge = session.scalar(
        select(ContactMerge).where(
            ContactMerge.id == merge_id,
            ContactMerge.tenant_id == actor.tenant_id,
        )
    )
    if merge is None:
        raise MergeNotFoundError()
    if merge.reverted_at is not None:
        raise MergeError("Merge has already been reverted.")

    survivor = session.get(Contact, merge.survivor_id)
    merged = session.get(Contact, merge.merged_id)
    if survivor is None or merged is None:
        raise ContactNotFoundError()
    if survivor.tenant_id != actor.tenant_id or merged.tenant_id != actor.tenant_id:
        raise MergeError("Cross-tenant unmerge refused.")

    evidence = merge.evidence or {}
    moved_method_ids = [UUID(v) for v in evidence.get("moved_method_ids", [])]
    repointed_opportunity_ids = [
        UUID(v) for v in evidence.get("repointed_opportunity_ids", [])
    ]

    # Restore methods to the merged contact.
    for mid in moved_method_ids:
        method = session.get(ContactMethod, mid)
        if method is not None:
            method.contact_id = merged.id

    # Restore opportunities.
    for oid in repointed_opportunity_ids:
        opp = session.get(Opportunity, oid)
        if opp is not None:
            opp.contact_id = merged.id

    # Restore contact status.
    merged.status = evidence.get("merged_previous_status", ContactStatus.ACTIVE.value)
    merged.display_name = evidence.get(
        "merged_previous_display_name", merged.display_name
    )
    merged.merged_into_id = None
    merged.updated_at = utcnow()

    merge.reverted_at = utcnow()
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise MergeError("Unmerge conflicted with existing contact methods.") from exc
    session.refresh(merge)
    return merge


# --------------------------------------------------------------------------- #
# opportunities
# --------------------------------------------------------------------------- #


def open_opportunity(
    session: Session,
    *,
    actor: User,
    contact_id: UUID,
    project_id: UUID,
    from_lead_id: UUID | None = None,
    owner_user_id: UUID | None = None,
    budget_min: int | None = None,
    budget_max: int | None = None,
    preferred_configuration: str | None = None,
    source: str | None = None,
    value_paise: int | None = None,
) -> Opportunity:
    """Open an opportunity; idempotent on from_lead_id (one ACTIVE per lead).

    Enforces one ACTIVE opportunity per (contact, project) when no lead is
    supplied, and one per (contact, project, lead) when a lead is supplied.
    """
    contact = session.scalar(
        select(Contact).where(
            Contact.id == contact_id, Contact.tenant_id == actor.tenant_id
        )
    )
    if contact is None:
        raise ContactNotFoundError()
    project = session.scalar(
        select(Project).where(
            Project.id == project_id, Project.tenant_id == actor.tenant_id
        )
    )
    if project is None:
        raise OpportunityConflictError("Project not found in tenant.")

    # Idempotency: same from_lead twice returns the same row.
    if from_lead_id is not None:
        existing = session.scalar(
            select(Opportunity).where(
                Opportunity.tenant_id == actor.tenant_id,
                Opportunity.lead_id == from_lead_id,
            )
        )
        if existing is not None:
            return existing

    # One ACTIVE opportunity per (contact, project[, lead]).
    conditions = [
        Opportunity.tenant_id == actor.tenant_id,
        Opportunity.contact_id == contact_id,
        Opportunity.project_id == project_id,
        Opportunity.stage.in_(_ACTIVE_OPPORTUNITY_STAGES),
    ]
    if from_lead_id is None:
        conditions.append(Opportunity.lead_id.is_(None))
    active = session.scalar(select(Opportunity).where(*conditions))
    if active is not None:
        return active

    opp = Opportunity(
        tenant_id=actor.tenant_id,
        contact_id=contact_id,
        project_id=project_id,
        lead_id=from_lead_id,
        stage=OpportunityStage.NEW.value,
        owner_user_id=owner_user_id if owner_user_id is not None else actor.id,
        budget_min=budget_min,
        budget_max=budget_max,
        preferred_configuration=preferred_configuration,
        source=source,
        value_paise=value_paise,
    )
    session.add(opp)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise OpportunityConflictError() from exc
    session.refresh(opp)
    return opp


def convert_lead(session: Session, *, actor: User, lead_id: UUID) -> Opportunity:
    """Idempotently convert a lead into contact + method + opportunity.

    The lead row is NOT modified (additive rule). Link is stored only on
    ``Opportunity.lead_id``.
    """
    lead = session.scalar(
        select(Lead).where(Lead.id == lead_id, Lead.tenant_id == actor.tenant_id)
    )
    if lead is None:
        raise OpportunityConflictError("Lead not found in tenant.")

    existing = session.scalar(
        select(Opportunity).where(
            Opportunity.tenant_id == actor.tenant_id,
            Opportunity.lead_id == lead.id,
        )
    )
    if existing is not None:
        return existing

    contact, _method, _created = resolve_contact(
        session,
        tenant_id=actor.tenant_id,
        email=lead.email,
        phone=lead.phone,
        display_name=lead.full_name,
        provenance={
            "source": "lead_conversion",
            "evidence_ref": str(lead.id),
            "captured_at": utcnow().isoformat(),
        },
    )
    assert contact is not None
    if contact.display_name != lead.full_name and contact.display_name.startswith(
        ("uuid:",)
    ):
        contact.display_name = lead.full_name

    opp = open_opportunity(
        session,
        actor=actor,
        contact_id=contact.id,
        project_id=lead.project_id,
        from_lead_id=lead.id,
        budget_min=lead.budget_min,
        budget_max=lead.budget_max,
        preferred_configuration=lead.preferred_configuration,
        source=lead.source,
    )
    return opp


def update_opportunity(
    session: Session,
    *,
    actor: User,
    opportunity_id: UUID,
    fields: dict,
) -> Opportunity:
    opp = session.scalar(
        select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.tenant_id == actor.tenant_id,
        )
    )
    if opp is None:
        raise OpportunityNotFoundError()
    if not _is_admin(actor) and opp.owner_user_id != actor.id:
        raise CustomerAccessDeniedError()

    if "stage" in fields and fields["stage"] is not None:
        requested = fields["stage"]
        requested_value = (
            requested.value if isinstance(requested, OpportunityStage) else str(requested)
        )
        current = OpportunityStage(opp.stage)
        target = OpportunityStage(requested_value)
        if target != current:
            if target not in _ALLOWED_STAGE_TRANSITIONS.get(current, frozenset()):
                raise InvalidStageTransitionError(current.value, target.value)
            opp.stage = target.value

    for name in (
        "owner_user_id",
        "budget_min",
        "budget_max",
        "preferred_configuration",
        "loss_reason",
        "won_booking_id",
        "value_paise",
    ):
        if name in fields:
            setattr(opp, name, fields[name])

    opp.updated_at = utcnow()
    session.commit()
    session.refresh(opp)
    return opp


def list_opportunities(
    session: Session, *, actor: User, page: int, page_size: int
) -> OpportunityListResponse:
    conditions = [Opportunity.tenant_id == actor.tenant_id]
    if not _is_admin(actor):
        conditions.append(Opportunity.owner_user_id == actor.id)
    total = session.scalar(
        select(func.count()).select_from(Opportunity).where(*conditions)
    ) or 0
    items = list(
        session.scalars(
            select(Opportunity)
            .where(*conditions)
            .order_by(Opportunity.created_at.desc(), Opportunity.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return OpportunityListResponse(
        items=[OpportunityResponse.model_validate(o) for o in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )


def list_contacts(
    session: Session,
    *,
    actor: User,
    page: int,
    page_size: int,
    search: str | None = None,
) -> ContactListResponse:
    conditions = [
        Contact.tenant_id == actor.tenant_id,
        Contact.status != ContactStatus.MERGED.value,
    ]
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Contact.display_name.ilike(pattern),
                Contact.canonical_key.ilike(pattern),
            )
        )
    total = session.scalar(
        select(func.count()).select_from(Contact).where(*conditions)
    ) or 0
    items = list(
        session.scalars(
            select(Contact)
            .where(*conditions)
            .order_by(Contact.created_at.desc(), Contact.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return ContactListResponse(
        items=[ContactResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )


def customer_360(
    session: Session, *, tenant_id: UUID, contact_id: UUID
) -> Customer360Response:
    """Aggregate the contact 360 view (delegates to timeline module)."""
    return build_customer_360(session, tenant_id=tenant_id, contact_id=contact_id)


def merge_response(merge: ContactMerge) -> MergeResponse:
    return MergeResponse.model_validate(merge)
