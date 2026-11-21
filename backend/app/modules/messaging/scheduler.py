"""Messaging outbox scheduler: periodically dispatch queued deliveries."""

from __future__ import annotations

import asyncio
import logging

from app.db.session import SessionLocal
from app.modules.messaging.dispatcher import process_due_deliveries

logger = logging.getLogger("propflow.messaging.scheduler")


class MessagingDispatchScheduler:
    """Poll the global outbox (rows carry tenant_id) in an asyncio loop."""

    def __init__(self, poll_interval_seconds: int = 30, batch_size: int = 50) -> None:
        self.poll_interval = poll_interval_seconds
        self.batch_size = batch_size
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Messaging dispatcher started (poll_interval=%ds, batch=%d)",
            self.poll_interval,
            self.batch_size,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Messaging dispatcher stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await asyncio.to_thread(self._run_sync_check)
            except Exception as exc:
                logger.error("Messaging dispatch tick failed: %s", exc)
            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break

    def _run_sync_check(self) -> None:
        with SessionLocal() as session:
            counts = process_due_deliveries(session, batch_size=self.batch_size)
            if any(counts.values()):
                logger.info("Messaging dispatch results: %s", counts)


messaging_scheduler = MessagingDispatchScheduler()
