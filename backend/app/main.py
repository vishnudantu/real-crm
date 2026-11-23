"""FastAPI application factory and root endpoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import dispose_engine

logger = logging.getLogger(__name__)


class RootResponse(BaseModel):
    """Basic, non-sensitive application information."""

    status: Literal["ok"] = "ok"
    name: str
    environment: str
    api_version: str
    api_prefix: str
    docs_url: str


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the PropFlow FastAPI application."""

    app_settings = settings or get_settings()
    configure_logging(app_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "Starting %s (environment=%s, api_version=%s, debug=%s)",
            app_settings.app_name,
            app_settings.environment,
            app_settings.api_version,
            app_settings.debug,
        )
        if (
            getattr(app_settings, "reminder_scheduler_enabled", True)
            and app_settings.environment not in ("test", "testing")
        ):
            from app.modules.notifications.scheduler import reminder_scheduler

            reminder_scheduler.poll_interval = (
                app_settings.reminder_poll_interval_seconds
            )
            reminder_scheduler.start()

        if (
            getattr(app_settings, "messaging_dispatch_enabled", True)
            and app_settings.environment not in ("test", "testing")
        ):
            from app.modules.messaging.scheduler import messaging_scheduler

            messaging_scheduler.poll_interval = app_settings.messaging_dispatch_poll_interval_seconds
            messaging_scheduler.batch_size = app_settings.messaging_dispatch_batch_size
            messaging_scheduler.start()

        if (
            getattr(app_settings, "collections_reminder_enabled", True)
            and app_settings.environment not in ("test", "testing")
        ):
            from app.modules.collections.scheduler import collections_reminder_scheduler

            collections_reminder_scheduler.start()

        yield

        logger.info("Shutting down %s", app_settings.app_name)
        if (
            getattr(app_settings, "reminder_scheduler_enabled", True)
            and app_settings.environment not in ("test", "testing")
        ):
            from app.modules.notifications.scheduler import reminder_scheduler

            await reminder_scheduler.stop()

        if (
            getattr(app_settings, "messaging_dispatch_enabled", True)
            and app_settings.environment not in ("test", "testing")
        ):
            from app.modules.messaging.scheduler import messaging_scheduler

            await messaging_scheduler.stop()

        if (
            getattr(app_settings, "collections_reminder_enabled", True)
            and app_settings.environment not in ("test", "testing")
        ):
            from app.modules.collections.scheduler import collections_reminder_scheduler

            await collections_reminder_scheduler.stop()

        dispose_engine()

    application = FastAPI(
        title=app_settings.app_name,
        description="PropFlow real-estate lead-response and site-visit booking API.",
        version=app_settings.api_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        # PropFlow always returns its JSON error envelope. FastAPI's debug mode
        # would return HTML tracebacks for unexpected errors instead.
        debug=False,
    )
    application.state.settings = app_settings

    register_exception_handlers(application)

    # Widget endpoints serve third-party websites (the tenant's own domain), so
    # they intentionally allow any origin. Widget calls carry a tenant-scoped
    # bearer token rather than cookies, and no response sets credentials.
    from app.core.cors import PathCORSMiddleware

    application.add_middleware(
        PathCORSMiddleware,
        widget_prefix=f"{app_settings.api_v1_prefix}/widget/",
        allowed_origins=app_settings.cors_allowed_origins,
    )

    application.include_router(api_router, prefix=app_settings.api_v1_prefix)

    @application.get(
        "/",
        response_model=RootResponse,
        tags=["root"],
        summary="Application information",
    )
    def root() -> RootResponse:
        """Return basic application information for clients and operators."""

        return RootResponse(
            name=app_settings.app_name,
            environment=app_settings.environment,
            api_version=app_settings.api_version,
            api_prefix=app_settings.api_v1_prefix,
            docs_url="/docs",
        )

    return application


app = create_app()
