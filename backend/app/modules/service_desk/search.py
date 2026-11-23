"""Simple search and agent suggestion helpers for the knowledge base.

Search is deliberately a plain, SQLite-safe case-insensitive ``LIKE`` over the
title and body — the deployment engine is SQLite in tests/dev and PostgreSQL
in production, and neither the FTS5 extension nor pg_trgm is a dependency here.
Two safeguards make ``LIKE`` correct across both dialects:

1. ``lower()`` is applied to both sides so matching is case-insensitive without
   relying on the dialect's ``ILIKE`` (SQLite has none; PostgreSQL's ``LIKE`` is
   case-sensitive).
2. ``escape="\\\\"`` backs the pattern's wildcards so a literal ``%`` or ``_``
   typed by a user matches text, not a wildcard, and the escape character itself
   is doubled first.

Word splitting for suggestions is pure (no DB), so it is unit-testable on its
own and shared by the endpoint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Words shorter than this are too common to be signal ("the", "to", "of").
MIN_SUGGESTION_WORD_LENGTH = 3

# Cap the number of distinct query words so a pathological subject cannot
# blow up the scoring loop.
MAX_SUGGESTION_WORDS = 12

_STOP_WORDS = frozenset(
    {
        "the", "and", "for", "are", "but", "not", "you", "all", "any", "can",
        "had", "her", "was", "one", "our", "out", "day", "get", "has", "him",
        "his", "how", "its", "new", "now", "old", "see", "two", "way", "who",
        "did", "yes", "their", "there", "which", "would", "could", "about",
        "with", "from", "this", "that", "then", "them", "they", "what", "when",
        "where", "why", "will", "have", "were", "been", "into", "your",
    }
)

_WORD_PATTERN = re.compile(r"[a-z0-9]+")


def like_contains_pattern(term: str) -> str:
    """Build a wildcard-bounded, escape-ready ``LIKE`` pattern for ``term``.

    ``%`` and ``_`` inside the term are escaped so they match literally, and
    backslashes are doubled first. The caller must pass the pattern with
    ``escape="\\\\"`` to SQLAlchemy's ``contains``/``like`` constructs.
    """
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def split_subject_words(text: str) -> list[str]:
    """Lowercased alphanumeric words from ``text`` in first-seen order.

    Stop-words and tokens shorter than MIN_SUGGESTION_WORD_LENGTH are dropped;
    the result is capped at MAX_SUGGESTION_WORDS entries.
    """
    words: list[str] = []
    seen: set[str] = set()
    for match in _WORD_PATTERN.finditer(text.lower()):
        word = match.group()
        if len(word) < MIN_SUGGESTION_WORD_LENGTH or word in _STOP_WORDS:
            continue
        if word in seen:
            continue
        seen.add(word)
        words.append(word)
        if len(words) >= MAX_SUGGESTION_WORDS:
            break
    return words


@dataclass(frozen=True)
class SuggestionCandidate:
    """Minimal article view the scorer needs (kept protocol-free for testing)."""

    article_id: object
    title: str
    slug: str
    category: str
    body_markdown: str


def score_article(
    words: list[str], *, title: str, category: str, body_markdown: str
) -> int:
    """Weighted keyword score for one article against ticket subject words.

    Title matches count double (a shared title word is far stronger evidence
    than a body mention); category matches count x2 as well since KB categories
    are curated topics; each body occurrence counts 1. Repeated subject words
    never inflate the score because callers dedupe via split_subject_words.
    """
    title_lower = title.lower()
    category_lower = category.lower()
    body_lower = body_markdown.lower()
    score = 0
    for word in words:
        if word in title_lower:
            score += 2
        if word in category_lower:
            score += 2
        score += body_lower.count(word)
    return score


def top_suggestions(
    ticket_subject: str, articles: list[SuggestionCandidate]
) -> list[tuple[SuggestionCandidate, int]]:
    """Return up to 3 (article, score) pairs ranked by keyword score.

    Pure function: no session, no dialect. Zero-score articles are excluded so
    unrelated articles are never shown; ties fall back to the caller's order
    (stable sort) so results are deterministic.
    """
    words = split_subject_words(ticket_subject)
    if not words:
        return []
    ranked = sorted(
        (
            (
                score_article(
                    words, title=a.title, category=a.category, body_markdown=a.body_markdown
                ),
                index,
                a,
            )
            for index, a in enumerate(articles)
        ),
        key=lambda item: (-item[0], item[1]),
    )
    return [(article, score) for score, _index, article in ranked if score > 0][:3]
