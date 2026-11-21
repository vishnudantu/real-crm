"""Two-zone CORS middleware.

The general API keeps the configured origin allowlist (never wildcard).
Widget endpoints, embedded on third-party websites, use a permissive policy
with credentials disabled: widget sessions are bearer tokens, not cookies.
"""

from __future__ import annotations

from collections.abc import Iterable

from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


class PathCORSMiddleware:
    """Route widget paths to a permissive policy; everything else stays locked."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        widget_prefix: str,
        allowed_origins: Iterable[str],
    ) -> None:
        self.app = app
        origins = list(allowed_origins)
        self.widget_prefix = widget_prefix
        self.restricted = CORSMiddleware(
            app=self.app,
            allow_origins=origins,
            # Matches the application-wide policy: credentials are only ever
            # enabled for the configured allowlist, never for wildcard origins.
            allow_credentials="*" not in origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.widget = CORSMiddleware(
            app=self.app,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path.startswith(self.widget_prefix):
            await self.widget(scope, receive, send)
        else:
            await self.restricted(scope, receive, send)
