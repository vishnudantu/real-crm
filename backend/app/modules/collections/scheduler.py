"""Daily collections reminder scheduler (messaging scheduler pattern).

Evaluates installment due dates against each tenant's reminder policy once
per day and queues ``MessageDelivery`` rows through the existing outbox. The
existing ``MessagingDispatchScheduler`` remains solely responsible for
delivery and dispatch-time consent suppression; this job only enqueues.

The daily guard (one evaluation per calendar day per process) plus the
``collection_reminders`` unique key make repeated ticks idempotent.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime

from app.db.session import SessionLocal
from app.modules.collections.reminders import queue_all_tenants

logger = logging.getLogger("propflow.collections.scheduler")


class CollectionsReminderScheduler:
    """Poll daily; evaluate due dates and enqueue reminders via the outbox."""

    def __init__(self, poll_interval_seconds: int = 3600) -> None:
        self.poll_interval = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._last_evaluated: date | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Collections reminder scheduler started (poll_interval=%ds)", self.poll_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Collections reminder scheduler stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await asyncio.to_thread(self._run_sync_check)
            except Exception as exc:  # a failed day must not kill the loop
                logger.error("Collections reminder tick failed: %s", exc)
            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break

    def _run_sync_check(self) -> None:
        today = datetime.now(UTC).date()
        if self._last_evaluated == today:
            return
        with SessionLocal() as session:
            counts = queue_all_tenants(session, today=today)
            self._last_evaluated = today
            if counts["queued"]:
                logger.info("Collections reminders queued: %s", counts)


collections_reminder_scheduler = CollectionsReminderScheduler()
