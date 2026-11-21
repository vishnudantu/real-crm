"""Tenant HTTP exceptions."""

from fastapi import HTTPException, status


class TenantSlugAlreadyExistsError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "An organization with this slug already exists.")


class TenantNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Tenant not found.")


class TenantSuspendedError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, "This organization is inactive.")
