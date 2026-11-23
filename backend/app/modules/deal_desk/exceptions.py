"""Safe HTTP errors for deal-desk pricing and discount-policy violations."""

from fastapi import HTTPException, status


class CostSheetNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Cost sheet not found.")


class CostSheetAlreadyExistsError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT, "A cost sheet already exists for this scope."
        )


class CostBreakdownInvalidError(HTTPException):
    def __init__(self, detail: str = "The cost breakdown must carry non-negative integer components.") -> None:
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail)


class DiscountMatrixInvalidError(HTTPException):
    """The tenant's matrix definition itself is not policy-safe."""

    def __init__(self, detail: str) -> None:
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail)


class DiscountBandBlockedError(HTTPException):
    """The requested discount percent falls in a blocked band (or beyond)."""

    def __init__(self, percent: object, limit_percent: object) -> None:
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            f"A {percent}% discount exceeds the deal-desk policy limit of "
            f"{limit_percent}% and is blocked at creation.",
        )


class DiscountReasonRequiredError(HTTPException):
    """The matched band requires a written justification."""

    def __init__(self, band_number: int) -> None:
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            f"Band {band_number} discounts require a non-empty reason.",
        )


class DealQuoteNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Quote not found.")


class DealUnitNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Unit not found.")


class DealProjectNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Project not found.")


class QuoteNotQuotableError(HTTPException):
    """A quote already has an open discount request and cannot be re-raised."""

    def __init__(self) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT,
            "A discount request is already open for this quote.",
        )
