"""Guard the Alembic migration graph: exactly one head, valid linear chain.

A concurrent feature branch that points its migration at a non-head revision
creates TWO Alembic heads and breaks ``alembic upgrade head``. This test walks
the real ScriptDirectory so a fork is caught in CI before merge.
"""

from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _script_directory() -> ScriptDirectory:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return ScriptDirectory.from_config(config)


def test_migration_graph_has_exactly_one_head() -> None:
    scripts = _script_directory()
    heads = list(scripts.get_heads())
    assert len(heads) == 1, (
        f"Expected exactly one Alembic head, found {len(heads)}: {heads}. "
        "A feature branch likely pointed its migration at a non-head revision; "
        "repoint it at the current head to keep a single linear chain."
    )


def test_every_revision_has_a_known_parent() -> None:
    scripts = _script_directory()
    for revision in scripts.walk_revisions():
        if revision.down_revision is None:
            continue
        parents = (
            (revision.down_revision,)
            if isinstance(revision.down_revision, str)
            else tuple(revision.down_revision)
        )
        for parent in parents:
            assert scripts.get_revision(parent) is not None, (
                f"Revision {revision.revision} references missing parent {parent}."
            )


def test_solar_migration_is_in_the_chain() -> None:
    scripts = _script_directory()
    revisions = {rev.revision for rev in scripts.walk_revisions()}
    assert "c3a7f1d9e2b5" in revisions, (
        "Solar-facing migration c3a7f1d9e2b5 is missing from the Alembic chain."
    )
