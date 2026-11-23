"""The alembic chain must stay a single linear head.

Branches are how schema roll-outs silently diverge across deployments, so
this test walks every revision in backend/alembic/versions and fails if more
than one head exists. Adding a migration with an existing head as its
down_revision keeps this green; forking does not.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

VERSIONS_DIR = Path(__file__).resolve().parents[2] / "alembic" / "versions"


def _revisions() -> dict[str, str | None]:
    revisions: dict[str, str | None] = {}
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        # Each migration only needs its module-level identifiers; ``op`` is
        # injected by the runner and is never touched at import time.
        spec.loader.exec_module(module)
        revision = getattr(module, "revision", None)
        if revision is None:
            continue
        assert isinstance(revision, str)
        assert revision not in revisions, f"duplicate revision {revision}"
        revisions[revision] = getattr(module, "down_revision", None)
    assert revisions, "no migrations discovered"
    return revisions


def test_exactly_one_alembic_head() -> None:
    revisions = _revisions()
    children = {
        down for down in revisions.values() if down is not None
    }
    # ``down_revision`` may name a base that was squashed away in the past;
    # only heads are revisions nobody revises.
    heads = [revision for revision in revisions if revision not in children]
    assert len(heads) == 1, f"expected one head, found {heads}"


def test_head_is_kb_csat_migration() -> None:
    revisions = _revisions()
    # Every referenced parent must exist — a dangling down_revision means the
    # chain cannot run on a fresh database.
    missing = {
        down for down in revisions.values()
        if down is not None and down not in revisions
    }
    assert not missing, f"dangling down_revision(s): {missing}"
    children = {down for down in revisions.values() if down is not None}
    heads = [revision for revision in revisions if revision not in children]
    assert heads == ["a3f5c7e9b2d4"]
    assert len("a3f5c7e9b2d4") == 12
