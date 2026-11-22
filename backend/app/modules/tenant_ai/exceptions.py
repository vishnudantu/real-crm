"""HTTP exceptions raised by per-tenant AI provider administration."""

from fastapi import HTTPException, status


class TenantAIProviderNotFoundError(HTTPException):
    """No active AI provider is configured for the caller's tenant."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No AI provider is configured for this organization.",
        )


class TenantAIProviderConfigurationError(HTTPException):
    """The provider could not be securely configured or read back."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
