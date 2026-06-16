# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Regenerate the committed, freshness-checked catalogue artifacts.

``build_catalog`` writes each bundle's ``manifest.json`` + ``ro-crate-metadata.json``
and the top-level ``catalog/index.json``. Output is deterministic, so running it twice
yields byte-identical files and CI can assert ``git diff --exit-code``.
"""

from __future__ import annotations

from pathlib import Path

from .canonical import write_canonical_json
from .index import build_index
from .manifest import write_manifests
from .settings import DEFAULT_BASE_URL
from .store import (
    index_path,
    list_pipeline_ids,
    load_descriptor,
    pipeline_dir,
)


def build_catalog(root: Path, *, base_url: str = DEFAULT_BASE_URL, repository_version: str | None = None) -> list[str]:
    """Regenerate all per-bundle manifests and the catalogue index under *root*.

    Returns the sorted list of pipeline ids that were (re)built.
    """
    ids = list_pipeline_ids(root)
    for pipeline_id in ids:
        descriptor = load_descriptor(root, pipeline_id)
        write_manifests(pipeline_dir(root, pipeline_id), descriptor)
    index = build_index(root, base_url=base_url, repository_version=repository_version)
    write_canonical_json(index_path(root), index)
    return ids
