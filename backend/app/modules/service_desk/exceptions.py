"""HTTP exceptions for the service-desk module."""

from __future__ import annotations

from fastapi import HTTPException, status


class TicketNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found."
        )


class InvalidStatusTransitionError(HTTPException):
    def __init__(self, current: str, requested: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid ticket status transition from {current} to {requested}."
            ),
        )


class TicketAssigneeError(HTTPException):
    def __init__(self, detail: str = "The assignee must be an active staff user in your organization.") -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class CommentBodyError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Comment body must contain 1 to 4000 characters.",
        )
