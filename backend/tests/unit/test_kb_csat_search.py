"""Pure-function tests for KB search: word split, LIKE escaping, suggestions."""

from __future__ import annotations

import pytest

from app.modules.service_desk.search import (
    MAX_SUGGESTION_WORDS,
    SuggestionCandidate,
    like_contains_pattern,
    score_article,
    split_subject_words,
    top_suggestions,
)


def article(
    *, article_id: str = "a", title: str, category: str = "General", body: str = ""
) -> SuggestionCandidate:
    return SuggestionCandidate(
        article_id=article_id, title=title, slug=title.lower().replace(" ", "-"),
        category=category, body_markdown=body,
    )


class TestSplitSubjectWords:
    def test_lowercases_and_dedupes_in_first_seen_order(self) -> None:
        assert split_subject_words("Payment Payment payment DONE") == ["payment", "done"]

    def test_drops_stop_words_and_short_tokens(self) -> None:
        assert split_subject_words("the to of hi water leaking") == ["water", "leaking"]

    def test_punctuation_splits_words(self) -> None:
        assert split_subject_words("Reg-no: 1234, possession?") == ["reg", "1234", "possession"]

    def test_caps_at_max_words(self) -> None:
        words = split_subject_words(" ".join(f"word{i:03d}" for i in range(50)))
        assert len(words) == MAX_SUGGESTION_WORDS

    def test_empty_and_symbol_only_subjects(self) -> None:
        assert split_subject_words("") == []
        assert split_subject_words("!!! ??? --") == []


class TestLikeContainsPattern:
    def test_wraps_in_wildcards(self) -> None:
        assert like_contains_pattern("loan") == "%loan%"

    def test_escapes_wildcards_and_backslash(self) -> None:
        assert like_contains_pattern("50% off") == "%50\\% off%"
        assert like_contains_pattern("a_b") == "%a\\_b%"
        assert like_contains_pattern("back\\slash") == "%back\\\\slash%"


class TestScoreArticle:
    def test_title_match_outranks_body_mention(self) -> None:
        words = ["possession"]
        title_hit = score_article(
            words, title="Possession Letter Guide", category="Documents",
            body_markdown="x",
        )
        body_hit = score_article(
            words, title="Something Else", category="Documents",
            body_markdown="the possession letter is here",
        )
        assert title_hit > body_hit

    def test_category_match_counts(self) -> None:
        assert score_article(["loan"], title="X", category="Loan Help", body_markdown="") > 0

    def test_no_match_is_zero(self) -> None:
        assert score_article(["mango"], title="Loan", category="Docs", body_markdown="nope") == 0

    def test_repeated_body_hits_accumulate(self) -> None:
        once = score_article(["water"], title="Pipe", category="G", body_markdown="water")
        twice = score_article(["water"], title="Pipe", category="G", body_markdown="water water")
        assert twice == once + 1


class TestTopSuggestions:
    def test_returns_at_most_three_ranked(self) -> None:
        candidates = [
            article(article_id=str(i), title=f"Payment issue guide {i}", body="payment")
            for i in range(5)
        ]
        matches = top_suggestions("payment issue", candidates)
        assert len(matches) == 3

    def test_zero_score_articles_excluded(self) -> None:
        matches = top_suggestions(
            "possession letter", [article(title="Token Burn Calculator")]
        )
        assert matches == []

    def test_empty_subject_returns_empty(self) -> None:
        assert top_suggestions("", [article(title="Anything")]) == []

    def test_title_match_beats_body_match_in_ranking(self) -> None:
        body_only = article(article_id="1", title="Totally unrelated", body="water leak repair")
        title_hit = article(article_id="2", title="Water leak repair steps", body="x")
        matches = top_suggestions("water leak repair", [body_only, title_hit])
        assert [m.article_id for m, _score in matches] == ["2", "1"]

    def test_scores_are_reported(self) -> None:
        matches = top_suggestions(
            "payment", [article(article_id="p", title="Payment failed", body="payment")]
        )
        # title hit (+2) + one body occurrence (+1); category has no match.
        assert [(m.article_id, score) for m, score in matches] == [("p", 3)]

    def test_ties_preserve_input_order(self) -> None:
        first = article(article_id="1", title="Payment Guide")
        second = article(article_id="2", title="Payment Guide")
        matches = top_suggestions("payment", [first, second])
        assert [m.article_id for m, _s in matches] == ["1", "2"]


def test_like_pattern_round_trips_through_sqlite_like() -> None:
    """The escape contract we rely on must be what SQLite actually implements."""
    import sqlite3

    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE t (v TEXT)")
    connection.executemany(
        "INSERT INTO t VALUES (?)", [("50% off",), ("100 percent",), ("a_b",), ("axb",)]
    )
    rows = {}
    for needle in ("50% off", "100 percent", "a_b", "axb"):
        pattern = like_contains_pattern(needle)
        rows[needle] = connection.execute(
            "SELECT v FROM t WHERE lower(v) LIKE ? ESCAPE '\\'", (pattern.lower(),)
        ).fetchall()
    assert [r[0] for r in rows["50% off"]] == ["50% off"]
    assert [r[0] for r in rows["100 percent"]] == ["100 percent"]
    assert [r[0] for r in rows["a_b"]] == ["a_b"]
    assert [r[0] for r in rows["axb"]] == ["axb"]
