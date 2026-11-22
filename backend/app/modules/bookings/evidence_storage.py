"""Tenant-partitioned local storage for staff site-visit evidence uploads."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from app.core.config import get_settings

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
# Keep an allow-list of evidence content types (photos + pdf) at the boundary.
ALLOWED_CONTENT_TYPES = frozenset({
    "image/jpeg", "image/png", "image/webp", "application/pdf",
})
MAX_EVIDENCE_BYTES = 10 * 1024 * 1024  # 10 MB per artifact


def storage_root() -> Path:
    configured = Path(get_settings().visit_evidence_storage_dir)
    root = configured if configured.is_absolute() else _BACKEND_ROOT / configured
    return root.resolve()


def _relative_parts(relative_path: str) -> tuple[str, ...]:
    path = PurePosixPath(relative_path)
    if not relative_path or path.is_absolute() or "\\" in relative_path:
        raise ValueError("Evidence storage paths must be relative POSIX paths.")
    if any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("Evidence storage path contains an unsafe component.")
    if path.parts[0].endswith(":"):
        raise ValueError("Evidence storage path must not contain a drive.")
    return path.parts


def resolve_path(relative_path: str) -> Path:
    parts = _relative_parts(relative_path)
    root = storage_root()
    target = (root / Path(*parts)).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Evidence storage path escapes the configured root.")
    return target


def write_evidence(*, tenant_id: UUID, contents: bytes) -> tuple[str, str]:
    """Write evidence bytes and return (relative_path, sha256). Exclusive create."""
    relative_path = f"{tenant_id}/{uuid4()}"
    target = resolve_path(relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        output.write(contents)
    return relative_path, hashlib.sha256(contents).hexdigest()


def remove_evidence(relative_path: str) -> None:
    """Best-effort cleanup used only when a just-created DB transaction fails."""
    try:
        resolve_path(relative_path).unlink(missing_ok=True)
    except (OSError, ValueError):
        pass
