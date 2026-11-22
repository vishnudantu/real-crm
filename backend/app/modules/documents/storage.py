"""Tenant-partitioned local artifact storage with path traversal guards."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from app.core.config import get_settings

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


def storage_root() -> Path:
    configured = Path(get_settings().documents_storage_dir)
    root = configured if configured.is_absolute() else _BACKEND_ROOT / configured
    return root.resolve()


def _relative_parts(relative_path: str) -> tuple[str, ...]:
    path = PurePosixPath(relative_path)
    if not relative_path or path.is_absolute() or "\\" in relative_path:
        raise ValueError("Document storage paths must be relative POSIX paths.")
    if any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("Document storage path contains an unsafe component.")
    if path.parts[0].endswith(":"):
        raise ValueError("Document storage path must not contain a drive.")
    return path.parts


def resolve_path(relative_path: str) -> Path:
    """Resolve a stored path only when it remains below the configured root."""

    parts = _relative_parts(relative_path)
    root = storage_root()
    target = (root / Path(*parts)).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Document storage path escapes the configured root.")
    return target


def new_storage_path(tenant_id: UUID) -> str:
    return f"{tenant_id}/{uuid4()}.pdf"


def write_pdf(*, tenant_id: UUID, contents: bytes) -> tuple[str, str]:
    """Write immutable PDF bytes and return their relative path and SHA-256."""

    relative_path = new_storage_path(tenant_id)
    target = resolve_path(relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidental overwrites of evidence artifacts.
    with target.open("xb") as output:
        output.write(contents)
    return relative_path, hashlib.sha256(contents).hexdigest()


def remove_pdf(relative_path: str) -> None:
    """Best-effort cleanup used only when a just-created DB transaction fails."""

    try:
        resolve_path(relative_path).unlink(missing_ok=True)
    except (OSError, ValueError):
        # Never mask the original database/storage exception during rollback.
        pass
