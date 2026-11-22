"""HTTP exceptions raised by the internal team chat module."""

from __future__ import annotations

from fastapi import HTTPException, status


class ChatChannelNotFoundError(HTTPException):
    """The channel does not exist or belongs to another tenant."""

    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Chat channel not found.")


class ChatMessageNotFoundError(HTTPException):
    """The message does not exist or belongs to another tenant."""

    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Chat message not found.")


class ChatMembershipRequiredError(HTTPException):
    """The caller must be a member of the channel."""

    def __init__(
        self, message: str = "Join this channel before continuing."
    ) -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, message)


class ChatChannelPrivateError(ChatMembershipRequiredError):
    """Private channels cannot be joined without an invitation."""

    def __init__(self) -> None:
        super().__init__("This private channel requires an invitation.")


class ChatMessageEditForbiddenError(HTTPException):
    """Only the original sender may edit a message."""

    def __init__(self) -> None:
        super().__init__(
            status.HTTP_403_FORBIDDEN, "Only the message sender can edit this message."
        )


class ChatChannelNameConflictError(HTTPException):
    """The requested channel name is already in use within the tenant."""

    def __init__(self) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT, "A channel with this name already exists."
        )
