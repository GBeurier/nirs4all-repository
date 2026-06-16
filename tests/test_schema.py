# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Tests for the PipelineDescriptor model and the schema-version gate."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nirs4all_repository.schema import (
    SCHEMA_VERSION,
    PipelineDescriptor,
    SchemaVersionError,
    check_schema_version,
)


def _base(**overrides) -> dict:
    data = {
        "schema_version": 1,
        "id": "demo_pipe",
        "name": "Demo",
        "summary": "A demo.",
        "framework": "nirs4all",
        "kind": "recipe",
        "task": "regression",
        "version": "1.0.0",
        "license": "CeCILL-2.1 OR AGPL-3.0-or-later",
        "created_at": "2026-06-17",
        "authors": [{"name": "A"}],
        "recipe": {"format": "nirs4all/pipeline-config", "path": "pipeline.json"},
    }
    data.update(overrides)
    return data


def test_valid_descriptor():
    desc = PipelineDescriptor.model_validate(_base())
    assert desc.id == "demo_pipe"
    assert desc.is_open_license()


def test_id_must_be_slug():
    with pytest.raises(ValidationError):
        PipelineDescriptor.model_validate(_base(id="Bad-Id"))


def test_recipe_kind_rejects_artifacts():
    with pytest.raises(ValidationError):
        PipelineDescriptor.model_validate(
            _base(kind="recipe", artifacts=[{"name": "x", "backend": "joblib", "relpath": "artifacts/x", "sha256": "a" * 64, "size_bytes": 1}])
        )


def test_fitted_kind_requires_artifacts():
    with pytest.raises(ValidationError):
        PipelineDescriptor.model_validate(_base(kind="fitted"))


def test_fitted_with_inline_artifact_ok():
    desc = PipelineDescriptor.model_validate(
        _base(
            kind="fitted",
            artifacts=[{"name": "m.n4a", "backend": "n4a", "relpath": "artifacts/m.n4a", "sha256": "a" * 64, "size_bytes": 10, "storage": "inline"}],
        )
    )
    assert desc.artifacts[0].backend.value == "n4a"


def test_release_artifact_requires_download_url():
    with pytest.raises(ValidationError):
        PipelineDescriptor.model_validate(
            _base(
                kind="fitted",
                artifacts=[{"name": "m", "backend": "joblib", "relpath": "artifacts/m", "sha256": "a" * 64, "size_bytes": 10, "storage": "release"}],
            )
        )


def test_evaluation_requires_reference():
    with pytest.raises(ValidationError):
        PipelineDescriptor.model_validate(_base(evaluation={"metric": "rmse"}))


def test_unsafe_recipe_path_rejected():
    with pytest.raises(ValidationError):
        PipelineDescriptor.model_validate(_base(recipe={"format": "nirs4all/pipeline-config", "path": "../escape.json"}))


def test_publication_blockers_official_requires_validation():
    desc = PipelineDescriptor.model_validate(
        _base(
            provenance={"generated_by": "x"},
            governance={"status": "draft", "visibility": "public", "trust": "official"},
            reference={"source": "nirs4all-datasets", "name": "demo"},
            evaluation={"metric": "rmse", "status": "unvalidated"},
        )
    )
    blockers = desc.publication_blockers()
    assert any("validated" in b for b in blockers)


def test_publication_blockers_experimental_ok_without_validation():
    desc = PipelineDescriptor.model_validate(
        _base(provenance={"generated_by": "x"}, governance={"trust": "experimental"})
    )
    assert desc.publication_blockers() == []


def test_publication_blockers_closed_license():
    desc = PipelineDescriptor.model_validate(
        _base(license="Proprietary", provenance={"generated_by": "x"}, governance={"trust": "experimental"})
    )
    assert any("open license" in b for b in desc.publication_blockers())


def test_schema_version_gate():
    check_schema_version(SCHEMA_VERSION)
    with pytest.raises(SchemaVersionError):
        check_schema_version(SCHEMA_VERSION + 1)
    with pytest.raises(SchemaVersionError):
        check_schema_version(0)


def test_future_schema_version_rejected_in_descriptor():
    with pytest.raises(ValidationError):
        PipelineDescriptor.model_validate(_base(schema_version=SCHEMA_VERSION + 1))
