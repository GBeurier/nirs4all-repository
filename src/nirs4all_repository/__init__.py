# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""nirs4all-repository — the public, versioned repository of pre-configured NIRS pipelines.

Resolve pipelines by name (local checkout → wheel-bundled catalogue → remote), inspect
their metadata, and bridge them to ``nirs4all`` / ``dag-ml``. Importing this package is
cheap; ``numpy``/``nirs4all``/``dag-ml`` are imported only on the paths that need them.

Example:
    >>> import nirs4all_repository as n4r
    >>> [p["id"] for p in n4r.list(framework="nirs4all")]      # doctest: +SKIP
    >>> pipe = n4r.get("snv_savgol_pls")                        # doctest: +SKIP
    >>> config = pipe.to_nirs4all()                             # doctest: +SKIP
"""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any

from ._version import __version__
from .bridge import Pipeline
from .schema import PipelineDescriptor
from .settings import Settings, get_settings
from .store import (
    bundled_root,
    detect_root,
    load_descriptor,
    load_index,
    pipeline_dir,
)

__all__ = [
    "Pipeline",
    "PipelineDescriptor",
    "Settings",
    "get_settings",
    "list",
    "card",
    "get",
    "fetch",
    "__version__",
]


def _catalog_root(root: Path | None, settings: Settings) -> Path | None:
    """Return a local catalogue root (explicit/env → checkout detection)."""
    explicit = root if root is not None else settings.root
    detected = detect_root(explicit)
    if detected is not None and (detected / "pipelines").is_dir():
        return detected
    return None


def _load_index_any(root: Path | None, settings: Settings) -> dict[str, Any]:
    """Load the catalogue index from the best available source (local → bundled → remote)."""
    local = _catalog_root(root, settings)
    if local is not None and (local / "catalog" / "index.json").is_file():
        return load_index(local)
    bundled = bundled_root()
    if bundled is not None and (bundled / "catalog" / "index.json").is_file():
        return load_index(bundled)
    from .fetch import fetch_index

    return fetch_index(settings.base_url)


def list(  # noqa: A001 - deliberate public name, mirrors nirs4all-datasets
    *,
    framework: str | None = None,
    task: str | None = None,
    tag: str | None = None,
    kind: str | None = None,
    trust: str | None = None,
    root: str | Path | None = None,
) -> builtins.list[dict[str, Any]]:
    """Return catalogue entries matching the given filters (from the index)."""
    settings = get_settings()
    index = _load_index_any(Path(root) if root else None, settings)
    entries = builtins.list(index.get("pipelines", {}).values())

    def keep(entry: dict[str, Any]) -> bool:
        if framework is not None and entry.get("framework") != framework:
            return False
        if task is not None and entry.get("task") != task:
            return False
        if kind is not None and entry.get("kind") != kind:
            return False
        if trust is not None and entry.get("trust") != trust:
            return False
        return not (tag is not None and tag not in entry.get("tags", []))

    return sorted((entry for entry in entries if keep(entry)), key=lambda entry: entry["id"])


def card(name: str, *, root: str | Path | None = None) -> dict[str, Any]:
    """Return the full validated descriptor (as a dict) for the pipeline *name*."""
    settings = get_settings()
    descriptor = _resolve_descriptor(name, Path(root) if root else None, settings)
    return descriptor.model_dump(mode="json", exclude_none=True)


def _resolve_descriptor(name: str, root: Path | None, settings: Settings) -> PipelineDescriptor:
    local = _catalog_root(root, settings)
    if local is not None and (pipeline_dir(local, name) / "descriptor.yaml").is_file():
        return load_descriptor(local, name)
    bundled = bundled_root()
    if bundled is not None and (pipeline_dir(bundled, name) / "descriptor.yaml").is_file():
        return load_descriptor(bundled, name)
    # Remote: fetch the descriptor declared in the index, verify, and parse.
    import yaml

    from .fetch import fetch_verified

    index = _load_index_any(root, settings)
    entry = index.get("pipelines", {}).get(name)
    if entry is None:
        from .store import PipelineNotFound

        raise PipelineNotFound(f"pipeline {name!r} not found in the catalogue")
    block = entry["descriptor"]
    data = yaml.safe_load(fetch_verified(block["url"], block.get("sha256")))
    return PipelineDescriptor.model_validate(data)


def get(
    name: str,
    *,
    root: str | Path | None = None,
    cache_dir: str | Path | None = None,
    verify: bool = True,
    with_artifacts: bool = False,
) -> Pipeline:
    """Resolve the pipeline *name* and return a :class:`Pipeline` handle.

    Resolution is local-first (a checkout), then the wheel-bundled catalogue, then a
    remote download with SHA-256 verification into the cache.
    """
    settings = get_settings()
    root_path = Path(root) if root else None

    local = _catalog_root(root_path, settings)
    if local is not None and (pipeline_dir(local, name) / "descriptor.yaml").is_file():
        pipeline = Pipeline(load_descriptor(local, name), pipeline_dir(local, name))
        if verify:
            pipeline.verify()
        return pipeline

    bundled = bundled_root()
    if bundled is not None and (pipeline_dir(bundled, name) / "descriptor.yaml").is_file():
        pipeline = Pipeline(load_descriptor(bundled, name), pipeline_dir(bundled, name))
        if verify:
            pipeline.verify()
        return pipeline

    from .fetch import fetch_index, materialize_remote

    cache = Path(cache_dir) if cache_dir else settings.cache_dir
    index = fetch_index(settings.base_url)
    entry = index.get("pipelines", {}).get(name)
    if entry is None:
        from .store import PipelineNotFound

        raise PipelineNotFound(f"pipeline {name!r} not found in the remote catalogue")
    materialized = materialize_remote(entry, cache, with_artifacts=with_artifacts, verify=verify)
    descriptor = _descriptor_from_dir(materialized, name)
    pipeline = Pipeline(descriptor, materialized)
    if verify:
        pipeline.verify()
    return pipeline


def _descriptor_from_dir(directory: Path, name: str) -> PipelineDescriptor:
    from .store import CatalogError, load_descriptor_file

    descriptor = load_descriptor_file(directory / "descriptor.yaml")
    if descriptor.id != name:
        raise CatalogError(f"fetched descriptor id {descriptor.id!r} != requested {name!r}")
    return descriptor


def fetch(
    name: str,
    *,
    root: str | Path | None = None,
    cache_dir: str | Path | None = None,
    verify: bool = True,
    with_artifacts: bool = False,
) -> Path:
    """Materialise the bundle for *name* locally and return its directory path."""
    return get(name, root=root, cache_dir=cache_dir, verify=verify, with_artifacts=with_artifacts).path
