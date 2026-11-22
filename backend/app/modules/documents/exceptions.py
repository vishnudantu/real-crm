"""Document service errors mapped to safe HTTP responses."""

from __future__ import annotations

from fastapi import HTTPException, status


class DocumentNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Document not found.")


class ReceiptNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Receipt not found.")


class DocumentVoidedError(HTTPException):
    def __init__(self, reason: str) -> None:
        super().__init__(
            status.HTTP_410_GONE,
            f"This document was voided: {reason}",
        )


class DocumentTemplateNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "An active document template is required.")
