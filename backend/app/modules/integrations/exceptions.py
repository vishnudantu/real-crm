"""HTTP exceptions raised by external integration management."""

from fastapi import HTTPException, status


class IntegrationConnectionNotFoundError(HTTPException):
    """The requested connection does not exist in the caller's tenant."""

    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="Integration connection not found.")


class IntegrationConnectionConflictError(HTTPException):
    """The globally unique provider account belongs to another configuration."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Meta page is already connected.",
        )


class IntegrationConfigurationError(HTTPException):
    """The connection could not be securely configured."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
