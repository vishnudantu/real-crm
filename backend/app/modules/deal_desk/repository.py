"""Tenant-scoped persistence for deal-desk artifacts.

Every lookup takes tenant_id and filters on it — cross-tenant reads return
None so the service can raise a shape-preserving 404, never a 403 that would
leak existence.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.deal_desk.models import CostSheet, DiscountMatrixBand, DiscountQuote


def get_cost_sheet(
    session: Session, *, tenant_id: UUID, sheet_id: UUID
) -> CostSheet | None:
    return session.scalar(
        select(CostSheet).where(
            CostSheet.id == sheet_id, CostSheet.tenant_id == tenant_id
        )
    )


def find_cost_sheet(
    session: Session, *, tenant_id: UUID, project_id: UUID, unit_id: UUID | None
) -> CostSheet | None:
    """The single sheet for one scope: unit-specific, or the project generic."""

    return session.scalar(
        select(CostSheet).where(
            CostSheet.tenant_id == tenant_id,
            CostSheet.project_id == project_id,
            CostSheet.unit_id.is_(None) if unit_id is None else CostSheet.unit_id == unit_id,
        )
    )


def list_cost_sheets(
    session: Session, *, tenant_id: UUID, project_id: UUID | None = None
) -> list[CostSheet]:
    statement = (
        select(CostSheet)
        .where(CostSheet.tenant_id == tenant_id)
        .order_by(CostSheet.created_at.desc(), CostSheet.id.desc())
    )
    if project_id is not None:
        statement = statement.where(CostSheet.project_id == project_id)
    return list(session.scalars(statement).unique().all())


def bands_for_tenant(session: Session, *, tenant_id: UUID) -> list[DiscountMatrixBand]:
    return list(
        session.scalars(
            select(DiscountMatrixBand)
            .where(DiscountMatrixBand.tenant_id == tenant_id)
            .order_by(DiscountMatrixBand.band_number.asc())
        ).unique().all()
    )


def get_quote(session: Session, *, tenant_id: UUID, quote_id: UUID) -> DiscountQuote | None:
    return session.scalar(
        select(DiscountQuote).where(
            DiscountQuote.id == quote_id, DiscountQuote.tenant_id == tenant_id
        )
    )


def list_quotes(
    session: Session, *, tenant_id: UUID, unit_id: UUID | None = None, limit: int = 50, offset: int = 0
) -> list[DiscountQuote]:
    statement = (
        select(DiscountQuote)
        .where(DiscountQuote.tenant_id == tenant_id)
        .order_by(DiscountQuote.created_at.desc(), DiscountQuote.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if unit_id is not None:
        statement = statement.where(DiscountQuote.unit_id == unit_id)
    return list(session.scalars(statement).unique().all())
