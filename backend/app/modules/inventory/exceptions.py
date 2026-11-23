"""Inventory-specific exceptions (house style: HTTPException carriers)."""

from __future__ import annotations

from fastapi import HTTPException, status


class UnitNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Unit not found.")


class ProjectNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Project not found.")


class UnitCodeAlreadyExistsError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "A unit with this code already exists in the project.")


class InvalidUnitTransitionError(HTTPException):
    def __init__(self, from_status: str, to_status: str) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT,
            f"Cannot move a unit from {from_status} to {to_status}.",
        )


class UnitNotAvailableError(HTTPException):
    def __init__(self, current_status: str) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT,
            f"Unit is not available for a hold (current status: {current_status}).",
        )


class DuplicateActiveHoldError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "This unit already has an active hold.")


class HoldNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Hold not found.")


class HoldNotActiveError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "This hold is no longer active.")


class HoldNotOwnedByActorError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, "This hold belongs to another user.")


class HoldExtensionLimitReachedError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "This hold has reached its maximum extensions.")


class BulkCreateRowError(ValueError):
    """A single row of a bulk create failed validation; never raised as HTTP."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class DiscountAlreadyRequestedError(HTTPException):
    """A discount request is already PENDING, APPROVED, or REJECTED on the unit."""

    def __init__(self) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT,
            "This unit already has a discount request; cancel it before raising another.",
        )
