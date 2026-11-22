"""Document issuance, snapshots, listing, download authorization, and voiding."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from threading import Lock
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.documents import repository, storage
from app.modules.documents.exceptions import (
    DocumentNotFoundError,
    DocumentVoidedError,
    ReceiptNotFoundError,
)
from app.modules.documents.models import (
    Document,
    DocumentStatus,
    DocumentTemplate,
    DocumentTemplateKey,
)
from app.modules.documents.pdf import (
    ascii_text,
    build_document_pdf,
    format_date,
    format_money,
)
from app.modules.messaging.engine import render_template
from app.modules.postsales import repository as postsales_repository
from app.modules.postsales.exceptions import InstallmentNotFoundError
from app.modules.postsales.models import Installment, PaymentPlan, Receipt
from app.modules.leads.models import Lead
from app.modules.projects.models import Project
from app.modules.tenancy.models import Tenant

logger = logging.getLogger(__name__)
_document_issue_lock = Lock()

DEMAND_LETTER_BODY = """Date: {issued_date}
Document: {document_number}

Dear {customer_name},

This is a payment demand for Unit {unit_code} at {project_name}, {project_location}.

Installment: {installment_number} - {milestone}
Due date: {due_date}
Installment amount: {amount}
Collected against this installment: {collected}
Outstanding against this installment: {outstanding}
Total booking consideration: {consideration}
Total collected across the plan: {plan_collected}
Total outstanding across the plan: {plan_outstanding}

Please pay the outstanding installment amount by the due date using the payment instructions below, quoting document {document_number} and installment reference {installment_id}.

Legal entity: {legal_entity_name}
Registered address: {legal_entity_address}
RERA number: {rera_number}
GSTIN: {gstin}

Payment instructions: {payment_instructions}
Bank: {bank_name}
Account name: {bank_account_name}
Account number: {bank_account_number}
IFSC: {bank_ifsc}

For questions or to report a payment already made, contact {support_contact}.

Issued by {issuer_name}.
This document records a generated payment demand. Delivery status is tracked separately by the messaging outbox."""

RECEIPT_BODY = """Receipt: {receipt_number}
Document: {document_number}
Payment date: {paid_date}

Received from {customer_name} for Unit {unit_code} at {project_name}, {project_location}.

Amount received: {amount}
Payment channel: {channel}
Payment reference: {payment_reference}
Installment: {installment_number} - {milestone}
Installment due date: {due_date}
Outstanding against this installment after this receipt: {outstanding}
Payment notes: {receipt_notes}

Received by {legal_entity_name}.
Registered address: {legal_entity_address}
GSTIN: {gstin}

This receipt confirms a payment posting recorded in the sales ledger. Its document hash and immutable issue snapshot are available through the authenticated proof endpoint."""


def _theme(tenant: Tenant) -> dict:
    return tenant.theme_json if isinstance(tenant.theme_json, dict) else {}


def _theme_value(theme: dict, key: str, default: str = "Not configured") -> str:
    value = theme.get(key, default)
    return ascii_text(value if value not in (None, "") else default)


def mask_account_number(value: object) -> str:
    """Keep only the final four account digits in PDFs and evidence snapshots."""

    digits = "".join(char for char in str(value or "") if char.isdigit())
    if not digits:
        return "Not configured"
    return f"XXXX{digits[-4:]}"


def _tenant_context(tenant: Tenant) -> dict[str, str]:
    theme = _theme(tenant)
    bank = theme.get("bank") if isinstance(theme.get("bank"), dict) else {}
    return {
        "tenant_name": ascii_text(tenant.brand_name or tenant.name),
        "legal_entity_name": _theme_value(theme, "legal_entity_name", tenant.name),
        "legal_entity_address": _theme_value(theme, "legal_entity_address"),
        "gstin": _theme_value(theme, "gstin"),
        "payment_instructions": _theme_value(theme, "payment_instructions"),
        "support_contact": _theme_value(theme, "support_contact"),
        "bank_name": _theme_value(bank, "name"),
        "bank_account_name": _theme_value(bank, "account_name"),
        "bank_account_number": mask_account_number(bank.get("account_number")),
        "bank_ifsc": _theme_value(bank, "ifsc"),
    }


def seed_default_templates(session: Session, *, tenant_id: UUID, actor_id: UUID | None = None) -> list[DocumentTemplate]:
    """Insert only missing key/version rows; never overwrite a tenant's edits."""

    templates = []
    for key, subject, body in (
        (DocumentTemplateKey.DEMAND_LETTER, "Payment Demand - {unit_code} - {milestone}", DEMAND_LETTER_BODY),
        (DocumentTemplateKey.RECEIPT, "Payment Receipt - {receipt_number}", RECEIPT_BODY),
    ):
        existing = session.query(DocumentTemplate).filter_by(
            tenant_id=tenant_id, key=key.value, version=1, locale="en"
        ).one_or_none()
        if existing is not None:
            templates.append(existing)
            continue
        template = DocumentTemplate(
            tenant_id=tenant_id,
            key=key.value,
            version=1,
            locale="en",
            subject=subject,
            body_template=body,
            is_active=True,
            created_by=actor_id,
        )
        session.add(template)
        session.flush()  # assign template.id before it can be referenced
        templates.append(template)
    return templates


def _booking_graph(session: Session, *, tenant_id: UUID, installment: Installment):
    plan = session.query(PaymentPlan).filter_by(
        id=installment.plan_id, tenant_id=tenant_id
    ).one_or_none()
    if plan is None:
        raise InstallmentNotFoundError()
    booking = postsales_repository.get_booking(
        session, plan.sale_booking_id, tenant_id=tenant_id
    )
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sale booking not found.")
    lead = session.query(Lead).filter_by(id=booking.lead_id, tenant_id=tenant_id).one_or_none()
    project = session.query(Project).filter_by(id=booking.project_id, tenant_id=tenant_id).one_or_none()
    if lead is None or project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking customer or project not found.")
    return plan, booking, lead, project


def _financial_context(session: Session, *, tenant_id: UUID, plan: PaymentPlan) -> dict[str, int]:
    installments = [item for item in plan.installments]
    paid_map = postsales_repository.paid_map_for_plan(
        session, [plan.id], tenant_id=tenant_id
    )
    return {
        "total_planned_paise": sum(item.amount_paise for item in installments),
        "total_collected_paise": sum(paid_map.values()),
        "paid_map": paid_map,
    }


def _demand_payload(
    session: Session, *, actor, installment: Installment, tenant: Tenant
) -> dict:
    plan, booking, lead, project = _booking_graph(
        session, tenant_id=actor.tenant_id, installment=installment
    )
    financial = _financial_context(session, tenant_id=actor.tenant_id, plan=plan)
    paid_map = financial["paid_map"]
    collected = paid_map.get(installment.id, 0)
    outstanding = max(0, installment.amount_paise - collected)
    unit = booking.unit_number
    if booking.unit_id is not None:
        # The canonical code supplements, but never mutates, the legacy booking text.
        from app.modules.inventory.models import PropertyUnit

        property_unit = session.query(PropertyUnit).filter_by(
            id=booking.unit_id, tenant_id=actor.tenant_id
        ).one_or_none()
        if property_unit is not None:
            unit = property_unit.internal_code
    payload = {
        "installment_id": str(installment.id),
        "installment_number": str(installment.sequence_no),
        "milestone": ascii_text(installment.milestone),
        "due_date": format_date(installment.due_on),
        "due_on": installment.due_on.isoformat(),
        "amount_paise": installment.amount_paise,
        "amount": format_money(installment.amount_paise),
        "collected_paise": collected,
        "collected": format_money(collected),
        "outstanding_paise": outstanding,
        "outstanding": format_money(outstanding),
        "consideration_paise": booking.consideration_paise,
        "consideration": format_money(booking.consideration_paise),
        "plan_collected_paise": financial["total_collected_paise"],
        "plan_collected": format_money(financial["total_collected_paise"]),
        "plan_outstanding_paise": max(0, financial["total_planned_paise"] - financial["total_collected_paise"]),
        "plan_outstanding": format_money(max(0, financial["total_planned_paise"] - financial["total_collected_paise"])),
        "customer_name": ascii_text(lead.full_name),
        "customer_email": ascii_text(lead.email or ""),
        "customer_phone": ascii_text(lead.phone or ""),
        "unit_code": ascii_text(unit),
        "unit_number": ascii_text(booking.unit_number),
        "project_name": ascii_text(project.name),
        "project_location": ascii_text(project.location),
        "rera_number": ascii_text(project.rera_number or "Not configured"),
        "issuer_name": ascii_text(getattr(actor, "full_name", "System")),
    }
    payload.update(_tenant_context(tenant))
    return payload


def _receipt_payload(session: Session, *, actor, receipt: Receipt, tenant: Tenant) -> dict:
    installment = postsales_repository.get_installment(
        session, receipt.installment_id, tenant_id=actor.tenant_id
    )
    if installment is None:
        raise InstallmentNotFoundError()
    payload = _demand_payload(session, actor=actor, installment=installment, tenant=tenant)
    payload.update({
        "receipt_id": str(receipt.id),
        "receipt_number": ascii_text(receipt.receipt_number),
        "receipt_amount_paise": receipt.amount_paise,
        "amount": format_money(receipt.amount_paise),
        "channel": ascii_text(receipt.channel),
        "payment_reference": ascii_text(receipt.reference or "Not provided"),
        "receipt_notes": ascii_text(receipt.notes or ""),
        "paid_date": format_date(receipt.paid_at),
        "paid_at": receipt.paid_at.isoformat(),
    })
    return payload


def _queue_document_event(session: Session, *, document: Document) -> None:
    """Queue only configured outbox rules; provider acceptance is not claimed here."""

    try:
        from app.modules.messaging.engine import emit_event

        payload = document.payload_snapshot
        event = (
            "document.demand_letter_issued"
            if document.kind == DocumentTemplateKey.DEMAND_LETTER.value
            else "document.receipt_issued"
        )
        emit_event(
            session,
            tenant_id=document.tenant_id,
            event=event,
            context={
                "entity_type": "document",
                "entity_id": document.id,
                "document_number": document.document_number,
                "document_id": str(document.id),
                "document_kind": document.kind,
                "template_version": document.template_version,
                "customer_name": payload.get("customer_name"),
                "project_name": payload.get("project_name"),
                "unit_code": payload.get("unit_code"),
                "amount": payload.get("amount"),
                "due_date": payload.get("due_date"),
                "to_address": payload.get("customer_email") or payload.get("customer_phone"),
            },
        )
    except Exception as exc:
        # A missing optional integration must not invalidate the generated evidence.
        logger.warning("Could not queue document messaging event: %s", exc)


def _issue_document(
    session: Session, *, actor, kind: DocumentTemplateKey, reference_type: str,
    reference_id: UUID, payload: dict,
) -> Document:
    seed_default_templates(session, tenant_id=actor.tenant_id, actor_id=actor.id)
    template = repository.active_template(session, tenant_id=actor.tenant_id, key=kind.value)
    if template is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An active document template is required.")
    template_version = template.version
    existing = repository.document_for_reference(
        session, tenant_id=actor.tenant_id, kind=kind.value,
        reference_id=reference_id, template_version=template_version,
    )
    if existing is not None:
        return existing

    snapshot = dict(payload)
    snapshot["template_version"] = template_version
    snapshot["issued_at"] = datetime.now(UTC).isoformat()
    # Allocate placeholders before rendering: document number is part of the evidence body.
    snapshot["document_number"] = "PENDING"
    snapshot["issued_date"] = format_date(datetime.now(UTC))

    def issue() -> Document:
        repository.lock_document_allocation(session, tenant_id=actor.tenant_id)
        duplicate = repository.document_for_reference(
            session, tenant_id=actor.tenant_id, kind=kind.value,
            reference_id=reference_id, template_version=template.version,
        )
        if duplicate is not None:
            return duplicate
        number = repository.next_document_number(
            session, tenant_id=actor.tenant_id, kind=kind.value
        )
        snapshot["document_number"] = number
        body = render_template(template.body_template, snapshot)
        subject = render_template(template.subject, snapshot)
        pdf_bytes = build_document_pdf(title=number, subject=subject, body=body)
        relative_path, digest = storage.write_pdf(tenant_id=actor.tenant_id, contents=pdf_bytes)
        try:
            document = Document(
                tenant_id=actor.tenant_id,
                kind=kind.value,
                reference_type=reference_type,
                reference_id=reference_id,
                template_id=template.id,
                template_version=template.version,
                document_number=number,
                status=DocumentStatus.ISSUED.value,
                storage_path=relative_path,
                content_sha256=digest,
                payload_snapshot=snapshot,
                issued_by=actor.id,
                issued_at=datetime.fromisoformat(snapshot["issued_at"]),
                created_at=datetime.fromisoformat(snapshot["issued_at"]),
                updated_at=datetime.fromisoformat(snapshot["issued_at"]),
            )
            session.add(document)
            session.flush()  # materialize document.id for outbox entity linkage
            _queue_document_event(session, document=document)
            session.commit()
            session.refresh(document)
            return document
        except Exception:
            session.rollback()
            storage.remove_pdf(relative_path)
            raise

    try:
        if session.get_bind().dialect.name == "sqlite":
            with _document_issue_lock:
                return issue()
        return issue()
    except IntegrityError:
        # Another worker won the same reference/version. Preserve idempotency.
        session.rollback()
        existing = repository.document_for_reference(
            session, tenant_id=actor.tenant_id, kind=kind.value,
            reference_id=reference_id, template_version=template_version,
        )
        if existing is not None:
            return existing
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Document issuance conflicted with a concurrent request. Retry the request.",
        ) from None


def issue_demand_letter(session: Session, *, actor, installment_id: UUID) -> Document:
    installment = postsales_repository.get_installment(
        session, installment_id, tenant_id=actor.tenant_id
    )
    if installment is None:
        raise InstallmentNotFoundError()
    tenant = session.get(Tenant, actor.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")
    payload = _demand_payload(session, actor=actor, installment=installment, tenant=tenant)
    return _issue_document(
        session, actor=actor, kind=DocumentTemplateKey.DEMAND_LETTER,
        reference_type="installment", reference_id=installment.id, payload=payload,
    )


def issue_receipt_pdf(session: Session, *, actor, receipt_id: UUID) -> Document:
    receipt = session.query(Receipt).filter_by(id=receipt_id, tenant_id=actor.tenant_id).one_or_none()
    if receipt is None:
        raise ReceiptNotFoundError()
    tenant = session.get(Tenant, actor.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")
    payload = _receipt_payload(session, actor=actor, receipt=receipt, tenant=tenant)
    return _issue_document(
        session, actor=actor, kind=DocumentTemplateKey.RECEIPT,
        reference_type="receipt", reference_id=receipt.id, payload=payload,
    )


def list_documents(session: Session, *, tenant_id: UUID, kind: str | None = None, reference_id: UUID | None = None) -> list[Document]:
    return repository.list_documents(session, tenant_id=tenant_id, kind=kind, reference_id=reference_id)


def get_document(session: Session, document_id: UUID, *, tenant_id: UUID) -> Document:
    document = repository.get_document(session, document_id, tenant_id=tenant_id)
    if document is None:
        raise DocumentNotFoundError()
    return document


def get_document_for_download(session: Session, document_id: UUID, *, tenant_id: UUID):
    document = get_document(session, document_id, tenant_id=tenant_id)
    if document.status == DocumentStatus.VOIDED.value:
        raise DocumentVoidedError(document.void_reason or "No reason recorded.")
    try:
        path = storage.resolve_path(document.storage_path)
    except ValueError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Document storage path is invalid.") from exc
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document file not found.")
    return document, path


def mark_void(
    session: Session, *, actor, document_id: UUID, reason: str, commit: bool = True
) -> Document:
    """Void evidence; ``commit=False`` joins the caller's domain transaction."""

    document = get_document(session, document_id, tenant_id=actor.tenant_id)
    if document.status == DocumentStatus.VOIDED.value:
        return document
    document.status = DocumentStatus.VOIDED.value
    document.voided_at = datetime.now(UTC)
    document.void_reason = reason
    document.updated_at = document.voided_at
    session.add(document)
    if commit:
        session.commit()
        session.refresh(document)
    return document
