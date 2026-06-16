# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Canonical serialisation, hashing, and path-safety primitives.

These low-level helpers give every generated artifact byte-stable, reproducible
content so that a ``build`` followed by ``git diff --exit-code`` is a meaningful
freshness gate, and so any language reproduces identical bytes. They are the only
place the repository defines "what canonical JSON is" and "what a safe relative path
is".
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

#: A pipeline id / slug: lowercase alphanumerics joined by single underscores.
SLUG_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")

#: A SHA-256 hex digest.
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_CHUNK = 1 << 20


def is_slug(value: str) -> bool:
    """Return ``True`` if *value* is a valid pipeline id / slug."""
    return bool(SLUG_RE.match(value))


def is_sha256(value: str) -> bool:
    """Return ``True`` if *value* is a lowercase 64-hex SHA-256 digest."""
    return bool(SHA256_RE.match(value))


def is_safe_relpath(value: str) -> bool:
    """Return ``True`` if *value* is a safe relative path inside a bundle.

    A safe path is non-empty, relative (not absolute and not a drive/root under *either*
    POSIX or Windows semantics — so a leading ``/`` or ``C:\\`` is rejected on every
    platform), and never contains a ``..`` component (so it cannot escape the bundle
    root). This is the path half of the ``validate_portable`` admission rule, and it is
    deliberately platform-independent: ``Path("/x").is_absolute()`` is ``False`` on
    Windows, so the check must not rely on the native flavour alone.
    """
    if not value or value != value.strip():
        return False
    if value[0] in ("/", "\\"):
        return False
    win = PureWindowsPath(value)
    pos = PurePosixPath(value)
    if win.is_absolute() or pos.is_absolute() or win.drive:
        return False
    parts = set(win.parts) | set(pos.parts)
    return ".." not in parts and "" not in parts and bool(parts)


def canonical_json(obj: Any) -> str:
    """Serialise *obj* to canonical JSON text (UTF-8, sorted keys, trailing newline)."""
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def write_canonical_json(path: Path, obj: Any) -> None:
    """Write *obj* to *path* as canonical JSON, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(obj), encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of the file at *path* (streamed)."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def nirs4all_config_hash(steps: Any) -> str:
    """Return the 16-char nirs4all config fingerprint of a step list.

    Reproduces ``nirs4all.pipeline.config.pipeline_config.PipelineConfigs.get_hash``:
    the SHA-256 of ``json.dumps(steps, sort_keys=True, separators=(",", ":"))``,
    truncated to 16 hex characters. Kept independent of ``nirs4all`` so it works
    without the library installed.
    """
    payload = json.dumps(steps, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
