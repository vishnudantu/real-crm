"""Outbound provider contracts."""

from __future__ import annotations

from typing import Protocol


class Provider(Protocol):
    """A delivery provider returns an external message identifier."""

    def send(self, *, to: str, body: str, context: dict) -> str: ...


class ProviderConfigurationError(RuntimeError):
    """A live provider was selected without its required configuration."""
