"""Pluggable transcription + summarization provider interface.

A real provider (Whisper / a hosted LLM) implements :class:`TranscriptionProvider`.
This module never performs network I/O itself; the deterministic fake derives
all output from its inputs so tests are stable and offline.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any


class TranscriptionProvider(ABC):
    """Contract for turning an audio reference into a transcript + summary."""

    #: Stable identifier persisted on the transcript row.
    name: str = "abstract"

    @abstractmethod
    def transcribe(self, *, audio_ref: str, language: str) -> dict[str, Any]:
        """Return ``{"text": str, "segments": [{"start_ms", "end_ms", "speaker", "text"}]}``."""
        raise NotImplementedError

    @abstractmethod
    def summarize(self, *, transcript_text: str) -> dict[str, Any]:
        """Return ``{summary, requirements, objections, commitments, next_actions}``."""
        raise NotImplementedError


_BUDGET_RE = re.compile(
    r"budget[^.]*?((?:rs\.?|inr|₹)?\s*[\d,]+(?:\.\d+)?\s*(?:cr|crore|crores|l|lakh|lakhs)?)",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(r"(?:in|at|near|location[:\s]+)\s+([A-Z][a-zA-Z]+)", re.IGNORECASE)
_CONFIG_RE = re.compile(r"(\d+\s*bhk|\d\s*bhk|\d+bhk)", re.IGNORECASE)
_TIMELINE_RE = re.compile(
    r"((?:within|in|by)\s+(?:the\s+)?(?:next\s+)?\d+\s+(?:day|days|week|weeks|month|months))",
    re.IGNORECASE,
)


class DeterministicFakeProvider(TranscriptionProvider):
    """Offline, input-derived fake for tests and local development.

    ``transcribe`` echoes the audio reference into one stable segment and a
    text blob. ``summarize`` pattern-matches budget/location/configuration/
    timeline out of the transcript text so the extracted ``requirements`` and
    ``commitments`` are non-empty and input-derived.
    """

    name = "deterministic-fake"

    def __init__(self, *, canned_transcript: str | None = None) -> None:
        self._canned = canned_transcript

    def transcribe(self, *, audio_ref: str, language: str) -> dict[str, Any]:
        text = self._canned or (
            "Buyer: I am looking for a 3 BHK in Whitefield. "
            "My budget is around 1.5 crore and I want to move within the next 3 months. "
            "Agent: I will share matching options and schedule a site visit."
        )
        segment = {
            "start_ms": 0,
            "end_ms": max(len(text) * 50, 1000),
            "speaker": "mixed",
            "text": text,
        }
        return {"text": text, "segments": [segment]}

    def summarize(self, *, transcript_text: str) -> dict[str, Any]:
        text = transcript_text or ""
        requirements: dict[str, Any] = {}
        budget = _BUDGET_RE.search(text)
        if budget:
            requirements["budget"] = budget.group(1).strip()
        location = _LOCATION_RE.search(text)
        if location:
            requirements["location"] = location.group(1).strip()
        config = _CONFIG_RE.search(text)
        if config:
            requirements["configuration"] = config.group(1).upper().replace(" ", "")
        timeline = _TIMELINE_RE.search(text)
        if timeline:
            requirements["timeline"] = timeline.group(1).strip()

        commitments = [
            {"text": "Share matching options with the buyer.", "needs_review": False},
            {"text": "Schedule a site visit.", "needs_review": True},
        ]
        next_actions = ["Send curated property list.", "Book site visit slot."]
        objections: list[str] = []
        summary = (
            "Call covered a buyer enquiry. "
            + (
                f"Requirements: {requirements}."
                if requirements
                else "No explicit structured requirements detected."
            )
        )
        return {
            "summary": summary,
            "requirements": requirements,
            "objections": objections,
            "commitments": commitments,
            "next_actions": next_actions,
        }
