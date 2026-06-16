# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Remote resolution: download, verify, and cache bundles by name.

The remote path is used only when a pipeline is not available locally (checkout) or in
the wheel-bundled catalogue. Downloads are HTTPS-only and verified against the
published SHA-256 *before* use; cached under ``<cache>/<id>/<recipe_sha256>/`` so a
changed recipe or new version never reads a stale entry. Uses only the standard
library — no extra runtime dependency.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Any

from .canonical import sha256_bytes

_TIMEOUT = 30


class FetchError(Exception):
    """Raised on a download, scheme, or checksum failure."""


def _require_https(url: str) -> None:
    if not url.lower().startswith("https://"):
        raise FetchError(f"refusing non-HTTPS URL: {url!r}")


def http_get(url: str, *, timeout: int = _TIMEOUT) -> bytes:
    """GET *url* over HTTPS and return the raw bytes."""
    _require_https(url)
    request = urllib.request.Request(url, headers={"User-Agent": "nirs4all-repository"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - scheme checked above
        data: bytes = response.read()
    return data


def fetch_verified(url: str, expected_sha256: str | None, *, timeout: int = _TIMEOUT) -> bytes:
    """Download *url* and verify its SHA-256 against *expected_sha256* if provided."""
    data = http_get(url, timeout=timeout)
    if expected_sha256 is not None:
        actual = sha256_bytes(data)
        if actual != expected_sha256:
            raise FetchError(f"checksum mismatch for {url}: expected {expected_sha256}, got {actual}")
    return data


def fetch_index(base_url: str, *, timeout: int = _TIMEOUT) -> dict[str, Any]:
    """Fetch and parse ``{base_url}/data/index.json``."""
    import json

    data = http_get(f"{base_url.rstrip('/')}/data/index.json", timeout=timeout)
    parsed = json.loads(data)
    if not isinstance(parsed, dict):
        raise FetchError("remote index.json is not a JSON object")
    return parsed


def _write(dest: Path, data: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def materialize_remote(
    entry: dict[str, Any],
    cache_dir: Path,
    *,
    with_artifacts: bool = False,
    verify: bool = True,
    timeout: int = _TIMEOUT,
) -> Path:
    """Download an index *entry*'s bundle into the cache and return its directory.

    Always fetches the descriptor, recipe, and any non-artifact files; fetches artifact
    blobs only when *with_artifacts* is true.
    """
    pipeline_id = str(entry["id"])
    recipe = entry["recipe"]
    recipe_sha = str(recipe.get("sha256", "nohash"))
    target = cache_dir / pipeline_id / recipe_sha
    target.mkdir(parents=True, exist_ok=True)

    def grab(block: dict[str, Any]) -> None:
        expected = block.get("sha256") if verify else None
        data = fetch_verified(block["url"], expected, timeout=timeout)
        _write(target / block["relpath"], data)

    grab(entry["descriptor"])
    grab(recipe)
    for block in entry.get("files", []):
        is_artifact = block.get("backend") is not None
        if is_artifact and not with_artifacts:
            continue
        grab(block)
    return target
