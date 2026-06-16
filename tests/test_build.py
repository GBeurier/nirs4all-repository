# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Tests for manifest/RO-Crate/index generation: determinism and tamper-evidence."""

from __future__ import annotations

from nirs4all_repository.builder import build_catalog
from nirs4all_repository.manifest import build_manifest, verify_bundle
from nirs4all_repository.store import (
    GENERATED_FILES,
    index_path,
    load_descriptor,
    pipeline_dir,
)


def test_build_creates_manifests_and_index(make_catalog):
    root = make_catalog("demo_pipe")
    build_catalog(root)
    bundle = pipeline_dir(root, "demo_pipe")
    assert (bundle / "manifest.json").is_file()
    assert (bundle / "ro-crate-metadata.json").is_file()
    assert index_path(root).is_file()


def test_build_is_idempotent(make_catalog):
    root = make_catalog("demo_pipe")
    build_catalog(root)
    snapshot = {p: p.read_bytes() for p in root.rglob("*.json")}
    build_catalog(root)
    after = {p: p.read_bytes() for p in root.rglob("*.json")}
    assert snapshot == after


def test_manifest_excludes_generated_files(make_catalog):
    root = make_catalog("demo_pipe")
    build_catalog(root)
    descriptor = load_descriptor(root, "demo_pipe")
    manifest = build_manifest(pipeline_dir(root, "demo_pipe"), descriptor)
    listed = {record["relpath"] for record in manifest["files"]}
    assert not (listed & GENERATED_FILES)
    assert "descriptor.yaml" in listed
    assert "pipeline.json" in listed


def test_manifest_has_no_walltime(make_catalog):
    root = make_catalog("demo_pipe", descriptor_overrides={"created_at": "2020-01-01"})
    build_catalog(root)
    descriptor = load_descriptor(root, "demo_pipe")
    manifest = build_manifest(pipeline_dir(root, "demo_pipe"), descriptor)
    assert manifest["created_at"] == "2020-01-01"


def test_verify_detects_tamper(make_catalog):
    root = make_catalog("demo_pipe")
    build_catalog(root)
    descriptor = load_descriptor(root, "demo_pipe")
    bundle = pipeline_dir(root, "demo_pipe")
    assert verify_bundle(bundle, descriptor) == []
    # Tamper with the recipe after the manifest was written.
    (bundle / "pipeline.json").write_text('{"pipeline": [{"class": "sklearn.linear_model.Ridge"}]}\n', encoding="utf-8")
    problems = verify_bundle(bundle, descriptor)
    assert any("pipeline.json" in p for p in problems)


def test_generated_at_preserved_when_unchanged(make_catalog):
    root = make_catalog("demo_pipe")
    build_catalog(root)
    import json

    first = json.loads(index_path(root).read_text())["generated_at"]
    build_catalog(root)
    second = json.loads(index_path(root).read_text())["generated_at"]
    assert first == second
