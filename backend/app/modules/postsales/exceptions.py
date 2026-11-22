"""HTTP exceptions for the post-sales module."""

from __future__ import annotations

from fastapi import HTTPException, status


class SaleBookingNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Sale booking not found.")


class SaleBookingExistsError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT, "This lead already has a sale booking."
        )


class PaymentPlanNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Payment plan not found.")


class PaymentPlanAmountMismatchError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "Installment amounts must sum exactly to the sale consideration.",
        )


class InstallmentNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Installment not found.")


class ReceiptNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Receipt not found.")


class ReceiptAlreadyVoidedError(HTTPException):
    def __init__(self, reason: str) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT,
            f"Receipt is already voided. Original reason: {reason or 'No reason recorded.'}",
        )


class ReceiptAmountExceedsOutstandingError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "Receipt amount exceeds the outstanding balance of the installment.",
        )


class BrokerCommissionNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Broker commission not found.")
