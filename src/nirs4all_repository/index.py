# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Build the canonical-JSON ``catalog/index.json`` registry (the cross-language contract).

The index is the single machine-readable registry, served at ``/data/index.json`` and
bundled in the wheel. Generation is deterministic: ``generated_at`` is preserved from
the previous index when nothing else changed, so the file only changes when content
does and ``build && git diff --exit-code`` is a stable gate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._version import __version__
from .canonical import sha256_file
from .schema import SCHEMA_VERSION, PipelineDescriptor, utc_date
from .settings import DEFAULT_BASE_URL
from .store import (
    CARD_FILENAME,
    DESCRIPTOR_FILENAME,
    index_path,
    list_pipeline_ids,
    load_descriptor,
    pipeline_dir,
)


def _file_block(pipeline_path: Path, relpath: str, base_url: str, pipeline_id: str, **extra: Any) -> dict[str, Any]:
    path = pipeline_path / relpath
    block: dict[str, Any] = {
        "relpath": relpath,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "url": f"{base_url}/data/pipelines/{pipeline_id}/{relpath}",
    }
    block.update(extra)
    return block


def _entry(root: Path, pipeline_id: str, base_url: str) -> dict[str, Any]:
    descriptor: PipelineDescriptor = load_descriptor(root, pipeline_id)
    path = pipeline_dir(root, pipeline_id)

    files: list[dict[str, Any]] = []
    card = path / CARD_FILENAME
    if card.is_file():
        files.append(_file_block(path, CARD_FILENAME, base_url, pipeline_id, backend=None, storage="inline", download_url=None))
    for artifact in descriptor.artifacts:
        files.append(
            {
                "relpath": artifact.relpath,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
                "backend": artifact.backend.value,
                "storage": artifact.storage.value,
                "download_url": artifact.download_url,
                "url": (artifact.download_url or f"{base_url}/data/pipelines/{pipeline_id}/{artifact.relpath}"),
            }
        )

    evaluation: dict[str, Any] | None = None
    if descriptor.evaluation is not None:
        evaluation = {
            "metric": descriptor.evaluation.metric,
            "status": descriptor.evaluation.status.value,
            "expected": {key: {"value": value.value, "tol": value.tol} for key, value in descriptor.evaluation.expected.items()},
            "validated_at": descriptor.evaluation.validated_at,
        }

    fingerprints = dict(descriptor.provenance.fingerprints) if descriptor.provenance else {}

    return {
        "id": descriptor.id,
        "name": descriptor.name,
        "summary": descriptor.summary,
        "framework": descriptor.framework.value,
        "kind": descriptor.kind.value,
        "task": descriptor.task.value,
        "tags": list(descriptor.tags),
        "version": descriptor.version,
        "license": descriptor.license,
        "authors": [author.model_dump(exclude_none=True) for author in descriptor.authors],
        "descriptor": _file_block(path, DESCRIPTOR_FILENAME, base_url, pipeline_id),
        "recipe": _file_block(
            path,
            descriptor.recipe.path,
            base_url,
            pipeline_id,
            format=descriptor.recipe.format.value,
        ),
        "files": files,
        "reference": descriptor.reference.model_dump(exclude_none=True) if descriptor.reference else None,
        "evaluation": evaluation,
        "fingerprints": fingerprints,
        "trust": descriptor.governance.trust.value,
        "card_url": f"pipeline/{pipeline_id}.html",
    }


def build_index(root: Path, *, base_url: str = DEFAULT_BASE_URL, repository_version: str | None = None) -> dict[str, Any]:
    """Build the deterministic ``index.json`` content for the catalogue at *root*."""
    ids = list_pipeline_ids(root)
    pipelines = {pid: _entry(root, pid, base_url) for pid in ids}
    index: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "repository": "nirs4all-repository",
        "repository_version": repository_version or __version__,
        "generated_at": _preserved_generated_at(root, pipelines, base_url, repository_version or __version__),
        "base_url": base_url,
        "count": len(pipelines),
        "pipelines": pipelines,
    }
    return index


def _preserved_generated_at(root: Path, pipelines: dict[str, Any], base_url: str, repository_version: str) -> str:
    """Return the prior ``generated_at`` when content is unchanged, else today's date."""
    path = index_path(root)
    if path.is_file():
        try:
            import json

            previous = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            previous = None
        if isinstance(previous, dict):
            same = (
                previous.get("pipelines") == pipelines
                and previous.get("base_url") == base_url
                and previous.get("repository_version") == repository_version
                and previous.get("schema_version") == SCHEMA_VERSION
            )
            stamp = previous.get("generated_at")
            if same and isinstance(stamp, str):
                return stamp
    return utc_date()
