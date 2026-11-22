"""Voice intelligence service errors mapped to safe HTTP responses."""

from __future__ import annotations

from fastapi import HTTPException, status


class TranscriptNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Transcript not found.")


class RecordingNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Call recording not found.")


class SummaryNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Summary not found for this transcript.")
