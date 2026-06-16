# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Generation and verification of per-bundle ``manifest.json`` and RO-Crate metadata.

Both files are **deterministic**: they carry no wall-clock build time (``created_at``
comes from the authored descriptor) and list files in a stable order, so regenerating
them is idempotent and a ``git diff --exit-code`` freshness check is meaningful. Their
checksum coverage is exactly the bundle's *data files* (never the generated manifests
themselves).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .canonical import sha256_file, write_canonical_json
from .recipes import load_recipe_file, recipe_fingerprints
from .schema import SCHEMA_VERSION, PipelineDescriptor
from .store import (
    MANIFEST_FILENAME,
    ROCRATE_FILENAME,
    data_files,
)

_ENCODING_FORMATS = {
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".json": "application/json",
    ".md": "text/markdown",
    ".n4a": "application/zip",
    ".joblib": "application/octet-stream",
    ".onnx": "application/octet-stream",
    ".safetensors": "application/octet-stream",
}


def _encoding_format(relpath: str) -> str:
    return _ENCODING_FORMATS.get(Path(relpath).suffix.lower(), "application/octet-stream")


def _file_records(pipeline_path: Path, descriptor: PipelineDescriptor) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in data_files(pipeline_path, descriptor):
        relpath = path.relative_to(pipeline_path).as_posix()
        records.append(
            {
                "relpath": relpath,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return sorted(records, key=lambda record: record["relpath"])


def _resolved_fingerprints(pipeline_path: Path, descriptor: PipelineDescriptor) -> dict[str, str]:
    if descriptor.provenance and descriptor.provenance.fingerprints:
        return dict(sorted(descriptor.provenance.fingerprints.items()))
    recipe = load_recipe_file(pipeline_path / descriptor.recipe.path)
    return recipe_fingerprints(recipe, descriptor.recipe.format)


def build_manifest(pipeline_path: Path, descriptor: PipelineDescriptor) -> dict[str, Any]:
    """Build the deterministic ``manifest.json`` content for a bundle."""
    artifacts = [
        {
            "relpath": artifact.relpath,
            "backend": artifact.backend.value,
            "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes,
            "storage": artifact.storage.value,
            "download_url": artifact.download_url,
        }
        for artifact in descriptor.artifacts
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "id": descriptor.id,
        "framework": descriptor.framework.value,
        "kind": descriptor.kind.value,
        "pipeline_version": descriptor.version,
        "generated_by": descriptor.provenance.generated_by if descriptor.provenance else None,
        "created_at": descriptor.created_at,
        "fingerprints": _resolved_fingerprints(pipeline_path, descriptor),
        "files": _file_records(pipeline_path, descriptor),
        "artifacts": artifacts,
    }


def build_rocrate(pipeline_path: Path, descriptor: PipelineDescriptor) -> dict[str, Any]:
    """Build the RO-Crate 1.1 metadata content (tamper-evidence + provenance manifest)."""
    parts = []
    file_nodes: list[dict[str, Any]] = []
    for record in _file_records(pipeline_path, descriptor):
        relpath = record["relpath"]
        parts.append({"@id": relpath})
        file_nodes.append(
            {
                "@id": relpath,
                "@type": "File",
                "name": relpath,
                "sha256": record["sha256"],
                "dagml:sha256": record["sha256"],
                "contentSize": record["size_bytes"],
                "encodingFormat": _encoding_format(relpath),
            }
        )
    graph: list[dict[str, Any]] = [
        {
            "@type": "CreativeWork",
            "@id": "ro-crate-metadata.json",
            "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
            "about": {"@id": "./"},
        },
        {
            "@id": "./",
            "@type": ["Dataset", "ComputationalWorkflow"],
            "name": descriptor.name,
            "description": descriptor.summary,
            "version": descriptor.version,
            "license": descriptor.license,
            "dateCreated": descriptor.created_at,
            "hasPart": parts,
        },
        *file_nodes,
    ]
    return {
        "@context": [
            "https://w3id.org/ro/crate/1.1/context",
            {"dagml": "https://github.com/GBeurier/dag-ml/schemas#"},
        ],
        "@graph": graph,
    }


def write_manifests(pipeline_path: Path, descriptor: PipelineDescriptor) -> None:
    """Write ``manifest.json`` and ``ro-crate-metadata.json`` for a bundle."""
    write_canonical_json(pipeline_path / MANIFEST_FILENAME, build_manifest(pipeline_path, descriptor))
    write_canonical_json(pipeline_path / ROCRATE_FILENAME, build_rocrate(pipeline_path, descriptor))


def verify_bundle(pipeline_path: Path, descriptor: PipelineDescriptor) -> list[str]:
    """Recompute data-file digests and return any tamper/consistency problems.

    Compares the on-disk bytes against a freshly built manifest. An empty list means the
    bundle is internally consistent (its committed ``manifest.json`` need not exist yet;
    this checks the *bytes*, which ``build`` then records).
    """
    problems: list[str] = []
    fresh = {record["relpath"]: record for record in _file_records(pipeline_path, descriptor)}
    # Every declared inline artifact must exist and match its descriptor sha256.
    for artifact in descriptor.artifacts:
        if artifact.storage.value != "inline":
            continue
        blob = pipeline_path / artifact.relpath
        if not blob.is_file():
            problems.append(f"inline artifact missing on disk: {artifact.relpath}")
            continue
        if sha256_file(blob) != artifact.sha256:
            problems.append(f"inline artifact sha256 mismatch: {artifact.relpath}")
    # If a committed manifest exists, its file digests must match the current bytes.
    manifest_file = pipeline_path / MANIFEST_FILENAME
    if manifest_file.is_file():
        import json

        committed = json.loads(manifest_file.read_text(encoding="utf-8"))
        for record in committed.get("files", []):
            relpath = record["relpath"]
            current = fresh.get(relpath)
            if current is None:
                problems.append(f"manifest lists missing file: {relpath}")
            elif current["sha256"] != record.get("sha256"):
                problems.append(f"checksum mismatch for {relpath}")
    return problems
