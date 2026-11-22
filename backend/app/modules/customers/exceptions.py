"""HTTP exceptions for the customers module."""

from __future__ import annotations

from fastapi import HTTPException, status


class ContactNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found."
        )


class OpportunityNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found."
        )


class MergeNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact merge not found."
        )


class MergeError(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class InvalidStageTransitionError(HTTPException):
    def __init__(self, current: str, requested: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid opportunity stage transition from {current} to {requested}."
            ),
        )


class OpportunityConflictError(HTTPException):
    def __init__(self, detail: str = "An active opportunity already exists.") -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class ContactUpdateError(HTTPException):
    """A contact PATCH payload is empty or touches non-editable fields."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ContactConflictError(HTTPException):
    """Concurrent create collided; the identity is owned by another row."""

    def __init__(self, detail: str = "Contact already exists.") -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class CustomerAccessDeniedError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this contact.",
        )
