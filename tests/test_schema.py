# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Tests for the PipelineDescriptor model and the schema-version gate."""

from __future__ import annotations

import importlib

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import nirs4all_repository as n4r
from nirs4all_repository.cli import app
from nirs4all_repository.schema import (
    SCHEMA_VERSION,
    PipelineDescriptor,
    SchemaVersionError,
    check_schema_version,
)
from nirs4all_repository.store import load_descriptor_file


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


@pytest.mark.parametrize("framework,fmt", [
    ("nirs4all", "dag-ml/pipeline-dsl"),
    ("nirs4all", "dag-ml/compiled-artifact"),
    ("dag-ml", "nirs4all/pipeline-config"),
])
@pytest.mark.parametrize("spoof_field", ["name", "id"])
def test_framework_format_mismatch_refused_before_all_gates_and_strict(make_catalog, monkeypatch, framework, fmt, spoof_field):
    reference = "n4probe_pair.not_called"
    step = {"class": "sklearn.preprocessing.StandardScaler", spoof_field: reference}
    recipe = {"pipeline": [step]}
    if fmt == "dag-ml/compiled-artifact":
        recipe = {"graph": {"nodes": [{"kind": "transform", "operator": step, spoof_field: reference}]}, "campaign_template": {}}
    root = make_catalog(framework=framework, recipe=recipe, descriptor_overrides={
        "recipe": {"format": fmt, "path": "pipeline.json"}, "governance": {"trust": "experimental"},
    })
    message = "framework and recipe format must belong to the same owner"
    with pytest.raises(ValidationError, match=message):
        load_descriptor_file(root / "pipelines/demo_pipe/descriptor.yaml")
    validation = importlib.import_module("nirs4all_repository.validate")
    monkeypatch.setattr(validation, "_strict_check", lambda *args: pytest.fail("mismatched descriptor reached strict parsing"))
    report = validation.validate_pipeline(root, "demo_pipe", strict=True)
    assert not report.ok
    assert any(message in error for error in report.errors)
    for command in ("scan", "validate", "publish", "build"):
        args = [command, *([] if command == "build" else ["demo_pipe"]), "--root", str(root)]
        result = CliRunner().invoke(app, args)
        assert result.exit_code == 1, (command, result.output)
        assert message in result.output + str(result.exception)
    strict_result = CliRunner().invoke(app, ["validate", "demo_pipe", "--strict", "--root", str(root)])
    assert strict_result.exit_code == 1
    assert message in strict_result.output
    assert not (root / "pipelines/demo_pipe/manifest.json").exists()
    assert not (root / "catalog/index.json").exists()


@pytest.mark.parametrize("framework,fmt,recipe", [
    ("nirs4all", "nirs4all/pipeline-config", {"pipeline": [{"class": "sklearn.preprocessing.StandardScaler", "name": "My step"}]}),
    ("dag-ml", "dag-ml/pipeline-dsl", {"steps": [{"kind": "transform", "id": "node.id", "name": "display.name", "operator": "sklearn.preprocessing.StandardScaler"}]}),
    ("dag-ml", "dag-ml/compiled-artifact", {"graph": {"id": "graph.id", "nodes": [{"kind": "transform", "id": "node.id", "operator": "sklearn.preprocessing.StandardScaler"}]}, "campaign_template": {}}),
])
def test_matching_owner_pairs_pass_production_gates(make_catalog, framework, fmt, recipe):
    root = make_catalog(framework=framework, recipe=recipe, descriptor_overrides={
        "recipe": {"format": fmt, "path": "pipeline.json"}, "governance": {"trust": "experimental"},
    })
    for command in ("scan", "validate", "publish", "build"):
        result = CliRunner().invoke(app, [command, *([] if command == "build" else ["demo_pipe"]), "--root", str(root)])
        assert result.exit_code == 0, (command, result.output)
    pipeline = n4r.get("demo_pipe", root=root)
    assert pipeline.recipe() == recipe
    assert (pipeline.to_nirs4all() if framework == "nirs4all" else pipeline.to_dagml()) == recipe
