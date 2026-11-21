"""FastAPI dependencies enforcing operator identity and fine-grained permissions."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.operator.models import OperatorPermission, OperatorUser
from app.modules.operator.security import decode_operator_token

operator_bearer = HTTPBearer(auto_error=False, scheme_name="OperatorBearer")


def get_current_operator(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(operator_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> OperatorUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Operator authentication required.")
    try:
        operator_id = decode_operator_token(credentials.credentials)
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired operator token.") from None
    operator = db.get(OperatorUser, operator_id)
    if operator is None or not operator.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Operator account is inactive or unavailable.")
    return operator


def require_operator_permission(permission: OperatorPermission):
    def dependency(
        operator: Annotated[OperatorUser, Depends(get_current_operator)],
    ) -> OperatorUser:
        if not operator.allowed(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient operator permission.")
        return operator

    return dependency


CurrentOperator = Annotated[OperatorUser, Depends(get_current_operator)]
