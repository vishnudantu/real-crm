"""HTTP exceptions raised by the messaging module."""

from __future__ import annotations

from fastapi import HTTPException, status


class MessageTemplateNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Message template not found.")


class TriggerRuleNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Trigger rule not found.")


class MessageDeliveryNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Message delivery not found.")


class TriggerRuleTemplateMismatchError(HTTPException):
    """The rule's channel does not match the referenced template's channel."""

    def __init__(self) -> None:
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "The rule channel must match the selected template channel.",
        )


class SendTestRequiresBodyOrTemplateError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            "Provide either a template_id or a message body for the test send.",
        )
