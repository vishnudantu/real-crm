"""Staff handover workspace and read-only buyer possession timeline."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import ManagerUser, require_roles
from app.modules.handover import service
from enum import StrEnum

from app.modules.handover.models import HandoverStatus
from app.modules.handover.schemas import (
    BuyerCaseList, CompleteRequest, HandoverCaseCreate, HandoverCaseList,
    HandoverCasePatch, HandoverCaseResponse, HandoverChecklist, KeyCollect,
    KeyCreate, KeyPatch, KeyResponse, SnagCreate, SnagPatch, SnagResponse,
)
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/handover", tags=["handover"])
StaffReader = Annotated[User, Depends(require_roles(
    RoleName.ADMIN, RoleName.MANAGER, RoleName.SALES_EXECUTIVE
))]
BuyerReader = Annotated[User, Depends(require_roles(RoleName.BUYER))]
Db = Annotated[Session, Depends(get_db)]


class SnagAction(StrEnum):
    FIX = "fix"
    VERIFY = "verify"
    CLOSE = "close"


@router.get("/mine", response_model=BuyerCaseList)
def list_mine_endpoint(actor: BuyerReader, db: Db) -> BuyerCaseList:
    items = service.buyer_cases(db, actor=actor)
    return BuyerCaseList(items=items, total=len(items))


@router.get("/mine/snags/{snag_id}/photo")
def download_mine_photo_endpoint(snag_id: UUID, actor: BuyerReader, db: Db) -> FileResponse:
    snag, path = service.buyer_download_photo(db, actor=actor, snag_id=snag_id)
    return FileResponse(path, media_type=snag.photo_content_type, headers={
        "X-Content-Sha256": snag.photo_content_sha256 or "",
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/cases", response_model=HandoverCaseList)
def list_cases_endpoint(
    actor: StaffReader, db: Db,
    case_status: Annotated[HandoverStatus | None, Query(alias="status")] = None,
) -> HandoverCaseList:
    rows = service.list_cases(db, tenant_id=actor.tenant_id, status_filter=case_status)
    return HandoverCaseList(items=rows, total=len(rows))


@router.post("/cases", response_model=HandoverCaseResponse, status_code=status.HTTP_201_CREATED)
def create_case_endpoint(payload: HandoverCaseCreate, actor: ManagerUser, db: Db) -> HandoverCaseResponse:
    return service.create_case(db, actor=actor, payload=payload)


@router.get("/cases/{case_id}", response_model=HandoverCaseResponse)
def get_case_endpoint(case_id: UUID, actor: StaffReader, db: Db) -> HandoverCaseResponse:
    return service.get_case(db, tenant_id=actor.tenant_id, case_id=case_id)


@router.patch("/cases/{case_id}", response_model=HandoverCaseResponse)
def patch_case_endpoint(case_id: UUID, payload: HandoverCasePatch, actor: ManagerUser, db: Db) -> HandoverCaseResponse:
    return service.update_case(db, actor=actor, case_id=case_id, payload=payload)


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case_endpoint(case_id: UUID, actor: ManagerUser, db: Db) -> None:
    service.delete_case(db, actor=actor, case_id=case_id)


@router.get("/cases/{case_id}/checklist", response_model=HandoverChecklist)
def checklist_endpoint(case_id: UUID, actor: StaffReader, db: Db) -> HandoverChecklist:
    return service.build_checklist(db, tenant_id=actor.tenant_id, case_id=case_id)


@router.post("/cases/{case_id}/complete", response_model=HandoverCaseResponse)
def complete_endpoint(case_id: UUID, payload: CompleteRequest, actor: ManagerUser, db: Db) -> HandoverCaseResponse:
    return service.complete_case(db, actor=actor, case_id=case_id, override_reason=payload.override_reason)


@router.post("/cases/{case_id}/snags", response_model=SnagResponse, status_code=status.HTTP_201_CREATED)
def create_snag_endpoint(case_id: UUID, payload: SnagCreate, actor: ManagerUser, db: Db) -> SnagResponse:
    return service.create_snag(db, actor=actor, case_id=case_id, payload=payload)


@router.get("/cases/{case_id}/snags", response_model=list[SnagResponse])
def list_snags_endpoint(case_id: UUID, actor: StaffReader, db: Db) -> list[SnagResponse]:
    return service.list_snags(db, tenant_id=actor.tenant_id, case_id=case_id)


@router.patch("/snags/{snag_id}", response_model=SnagResponse)
def patch_snag_endpoint(snag_id: UUID, payload: SnagPatch, actor: ManagerUser, db: Db) -> SnagResponse:
    return service.update_snag(db, actor=actor, snag_id=snag_id, payload=payload)


@router.post("/snags/{snag_id}/photo", response_model=SnagResponse)
async def upload_photo_endpoint(snag_id: UUID, actor: ManagerUser, db: Db, request: Request) -> SnagResponse:
    return service.upload_snag_photo(
        db, actor=actor, snag_id=snag_id, contents=await request.body(),
        content_type=(request.headers.get("content-type") or "application/octet-stream").split(";")[0],
    )


@router.get("/snags/{snag_id}/photo")
def download_photo_endpoint(snag_id: UUID, actor: StaffReader, db: Db) -> FileResponse:
    snag, path = service.download_snag_photo(db, actor=actor, snag_id=snag_id)
    return FileResponse(path, media_type=snag.photo_content_type, headers={
        "X-Content-Sha256": snag.photo_content_sha256 or "",
        "X-Content-Type-Options": "nosniff",
    })


@router.post("/snags/{snag_id}/{action}", response_model=SnagResponse)
def transition_snag_endpoint(snag_id: UUID, action: SnagAction, actor: ManagerUser, db: Db) -> SnagResponse:
    return service.transition_snag(db, actor=actor, snag_id=snag_id, action=action.value)


@router.delete("/snags/{snag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_snag_endpoint(snag_id: UUID, actor: ManagerUser, db: Db) -> None:
    service.delete_snag(db, actor=actor, snag_id=snag_id)


@router.post("/cases/{case_id}/keys", response_model=KeyResponse, status_code=status.HTTP_201_CREATED)
def create_key_endpoint(case_id: UUID, payload: KeyCreate, actor: ManagerUser, db: Db) -> KeyResponse:
    return service.record_keys(db, actor=actor, case_id=case_id, payload=payload)


@router.get("/cases/{case_id}/keys", response_model=list[KeyResponse])
def list_keys_endpoint(case_id: UUID, actor: StaffReader, db: Db) -> list[KeyResponse]:
    return service.list_keys(db, tenant_id=actor.tenant_id, case_id=case_id)


@router.patch("/keys/{key_id}", response_model=KeyResponse)
def update_key_endpoint(key_id: UUID, payload: KeyPatch, actor: ManagerUser, db: Db) -> KeyResponse:
    return service.update_keys(db, actor=actor, key_id=key_id, payload=payload)


@router.post("/keys/{key_id}/collect", response_model=KeyResponse)
def collect_key_endpoint(key_id: UUID, payload: KeyCollect, actor: ManagerUser, db: Db) -> KeyResponse:
    return service.collect_keys(db, actor=actor, key_id=key_id, payload=payload)


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_key_endpoint(key_id: UUID, actor: ManagerUser, db: Db) -> None:
    service.delete_keys(db, actor=actor, key_id=key_id)
