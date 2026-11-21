"""FastAPI dependency that gates endpoints behind per-tenant feature flags.

A disabled feature returns 404 rather than 403 so the public API surface does
not disclose capabilities that exist but are not enabled for an organization.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.operator import features
from app.modules.users.models import User


def require_feature(feature_key: str):
    """Dependency factory enforcing one catalog feature for the caller's tenant."""

    def dependency(
        request: Request,
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> User:
        cache = request.scope.setdefault("propflow_features", {})
        if feature_key not in cache:
            cache[feature_key] = features.tenant_feature_state(
                db, tenant_id=current_user.tenant_id, key=feature_key
            )
        if not cache[feature_key]:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "This capability is not available for your organization.",
            )
        return current_user

    return dependency
