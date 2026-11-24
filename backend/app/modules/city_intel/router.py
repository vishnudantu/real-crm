"""City Intelligence Engine (Phase 1) — HTTP endpoints.

Permission-gated per the registry pattern: ``city_intel.read`` for reads,
``city_intel.manage`` for curated writes and fact generation. All queries are
tenant-scoped; cross-tenant projects resolve to 404.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.city_intel import service
from app.modules.city_intel.schemas import (
    AmenityCreateRequest,
    AmenityListResponse,
    AmenityResponse,
    ConnectivityResponse,
    DemandResponse,
    LocalityReportCreateRequest,
    LocalityReportListResponse,
    LocalityReportResponse,
)
from app.modules.users.models import User
from app.modules.users.permissions import CITY_INTEL_MANAGE, CITY_INTEL_READ

router = APIRouter(prefix="/city-intel", tags=["city-intelligence"])

Reader = Annotated[User, Depends(require_permission(CITY_INTEL_READ))]
Curator = Annotated[User, Depends(require_permission(CITY_INTEL_MANAGE))]


@router.get("/demand", response_model=DemandResponse, summary="Catchment demand by locality")
def demand_endpoint(reader: Reader, db: Annotated[Session, Depends(get_db)]) -> DemandResponse:
    rows = service.demand_by_locality(db, tenant_id=reader.tenant_id)
    return DemandResponse(items=rows, total=len(rows))


@router.get(
    "/projects/{project_id}/amenities",
    response_model=AmenityListResponse,
    summary="Curated points of interest near a project",
)
def list_amenities_endpoint(
    project_id: UUID, reader: Reader, db: Annotated[Session, Depends(get_db)]
) -> AmenityListResponse:
    rows = service.list_amenities(db, tenant_id=reader.tenant_id, project_id=project_id)
    return AmenityListResponse(items=rows, total=len(rows))


@router.post(
    "/amenities",
    response_model=AmenityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a curated point of interest (city_intel.manage)",
)
def add_amenity_endpoint(
    payload: AmenityCreateRequest, curator: Curator, db: Annotated[Session, Depends(get_db)]
) -> AmenityResponse:
    return service.add_amenity(db, actor=curator, payload=payload)


@router.get(
    "/projects/{project_id}/connectivity",
    response_model=ConnectivityResponse,
    summary="Connectivity score from curated POIs",
)
def connectivity_endpoint(
    project_id: UUID, reader: Reader, db: Annotated[Session, Depends(get_db)]
) -> ConnectivityResponse:
    return service.project_connectivity(db, tenant_id=reader.tenant_id, project_id=project_id)


@router.get(
    "/projects/{project_id}/reports",
    response_model=LocalityReportListResponse,
    summary="Source-verified locality reports",
)
def list_reports_endpoint(
    project_id: UUID, reader: Reader, db: Annotated[Session, Depends(get_db)]
) -> LocalityReportListResponse:
    rows = service.list_reports(db, tenant_id=reader.tenant_id, project_id=project_id)
    return LocalityReportListResponse(items=rows, total=len(rows))


@router.post(
    "/reports",
    response_model=LocalityReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Author a source-verified locality report (city_intel.manage)",
)
def create_report_endpoint(
    payload: LocalityReportCreateRequest, curator: Curator, db: Annotated[Session, Depends(get_db)]
) -> LocalityReportResponse:
    return service.create_report(db, actor=curator, payload=payload)


@router.post(
    "/projects/{project_id}/generate-facts",
    summary="Generate DRAFT locality facts (city_intel.manage)",
)
def generate_facts_endpoint(
    project_id: UUID, curator: Curator, db: Annotated[Session, Depends(get_db)]
) -> dict:
    facts = service.generate_facts(db, actor=curator, project_id=project_id)
    return {"generated": len(facts), "status": "DRAFT", "fact_ids": [str(f.id) for f in facts]}
