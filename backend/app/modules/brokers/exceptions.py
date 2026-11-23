"""Broker service errors mapped to safe HTTP responses."""

from __future__ import annotations

from fastapi import HTTPException, status


class BrokerNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "Broker not found.")
