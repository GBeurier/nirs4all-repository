# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Tests for the recipe class allow-list and the pickle-opcode scan."""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import pickle
import sys
import zipfile

import pytest
import yaml
from typer.testing import CliRunner

from nirs4all_repository.builder import build_catalog
from nirs4all_repository.cli import app
from nirs4all_repository.recipes import execution_requirements, validate_recipe_structure
from nirs4all_repository.schema import Framework, RecipeFormat
from nirs4all_repository.security import SecurityError, scan_config, scan_pickle_bytes
from nirs4all_repository.store import pipeline_dir
from nirs4all_repository.validate import validate_pipeline


class DangerousPickle:
    def __reduce__(self):
        return (os.system, ("echo hi",))


def _dangerous_pickle_payload() -> bytes:
    return pickle.dumps(DangerousPickle(), protocol=4)


def _zip_with_pickle_member(member_name: str, payload: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(member_name, payload)
    return buffer.getvalue()


def _attach_inline_artifact(root, pipeline_id: str, relpath: str, payload: bytes, *, backend: str = "joblib") -> None:
    bundle = pipeline_dir(root, pipeline_id)
    artifact_path = bundle / relpath
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(payload)

    descriptor_path = bundle / "descriptor.yaml"
    descriptor = yaml.safe_load(descriptor_path.read_text(encoding="utf-8"))
    descriptor["kind"] = "fitted"
    descriptor["artifacts"] = [
        {
            "name": "model",
            "backend": backend,
            "relpath": relpath,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
            "storage": "inline",
        }
    ]
    descriptor_path.write_text(yaml.safe_dump(descriptor, sort_keys=False), encoding="utf-8")


def test_scan_config_clean():
    recipe = {"pipeline": [{"class": "sklearn.preprocessing.MinMaxScaler"}, {"class": "nirs4all.operators.transforms.StandardNormalVariate"}]}
    result = scan_config(recipe, RecipeFormat.nirs4all_pipeline_config)
    assert result.ok, result.findings


def test_scan_config_blocks_injection():
    recipe = {"pipeline": [{"class": "os.system"}]}
    result = scan_config(recipe, RecipeFormat.nirs4all_pipeline_config)
    assert not result.ok
    assert any("os" in f for f in result.findings)


def test_scan_config_blocks_builtins_eval():
    recipe = {"pipeline": [{"class": "builtins.eval"}]}
    result = scan_config(recipe, RecipeFormat.nirs4all_pipeline_config)
    assert not result.ok


def test_scan_config_extra_allowlist_local_only():
    recipe = {"pipeline": [{"class": "mypackage.MyModel"}]}
    blocked = scan_config(recipe, RecipeFormat.nirs4all_pipeline_config)
    assert not blocked.ok
    allowed = scan_config(recipe, RecipeFormat.nirs4all_pipeline_config, extra_allowlist=("mypackage",))
    assert allowed.ok


@pytest.mark.parametrize("reference", ["builtins.eval", "subprocess.getoutput", "n4m:pls"])
@pytest.mark.parametrize("nest", [
    lambda r: {"params": {"func": r}},
    lambda r: {"model": {"params": {"estimator": r}}},
    lambda r: {"params": {"nested": [[r]]}},
    lambda r: {"finetune_params": {"func": r}},
    lambda r: {"train_params": {"func": r}},
    lambda r: {"merge": {"func": r}},
    lambda r: {"meta_model": {"params": {"func": r}}},
    lambda r: {"sample_augmentation": {"transformers": [r]}},
    lambda r: {"params": {"metadata": {"name": r, "description": r, "provenance": r, "id": r}}},
], ids=["func", "estimator", "lists", "finetune", "train", "merge", "meta_model", "augmentation", "arbitrary_param_metadata"])
def test_b3_step_subtrees_refused_by_scan_validate_and_publish(make_catalog, reference, nest):
    recipe = {"pipeline": [{"class": "sklearn.preprocessing.FunctionTransformer", **nest(reference)}]}
    validate_recipe_structure(recipe, RecipeFormat.nirs4all_pipeline_config)
    root = make_catalog(recipe=recipe, descriptor_overrides={"governance": {"trust": "experimental"}})
    report = validate_pipeline(root, "demo_pipe")
    assert not report.errors  # The rejection must come from scanning, not malformed input.
    assert any(reference in finding for finding in report.security_findings)
    for command in ("scan", "validate", "publish"):
        result = CliRunner().invoke(app, [command, "demo_pipe", "--root", str(root)])
        assert result.exit_code == 1, (command, result.output)
        assert reference in result.output
        assert "security scan clean" not in result.output
        assert "ready to publish" not in result.output


def test_b3_allowlisted_callable_and_root_metadata_remain_valid(make_catalog):
    # FunctionTransformer.func accepts this public callable; no execution is needed.
    recipe = {"name": "v1.2", "description": "data.csv", "provenance": {"version": "1.2", "source": "spectra.csv"},
              "pipeline": [{"name": "My step", "class": "sklearn.preprocessing.FunctionTransformer", "params": {"func": "sklearn.preprocessing.scale"}}]}
    root = make_catalog(recipe=recipe, descriptor_overrides={"governance": {"trust": "experimental"}})
    for command in ("scan", "validate", "publish"):
        result = CliRunner().invoke(app, [command, "demo_pipe", "--root", str(root)])
        assert result.exit_code == 0, (command, result.output)
    requirements = execution_requirements(recipe, Framework.nirs4all, RecipeFormat.nirs4all_pipeline_config)
    assert requirements["python_module_roots"] == ["sklearn"]
    assert "python_dependencies" in requirements["unknown"]


def test_b3_dag_identifiers_are_metadata_but_parameter_identifiers_are_scanned():
    recipe = {"id": "root.identifier", "steps": [{"kind": "transform", "id": "aug.synthetic", "name": "display.name",
              "operator": "sklearn.preprocessing.FunctionTransformer", "params": {"func": "sklearn.preprocessing.scale"}}]}
    assert scan_config(recipe, RecipeFormat.dagml_pipeline_dsl).ok
    recipe["steps"][0]["params"]["id"] = "builtins.eval"
    assert not scan_config(recipe, RecipeFormat.dagml_pipeline_dsl).ok


@pytest.mark.parametrize("step", [
    {"class": "sklearn.preprocessing.StandardScaler", "name": "n4probe_b4.not_called"},
    {"model": {"class": "sklearn.cross_decomposition.PLSRegression"}, "name": "n4probe_b4.not_called"},
    {"model": {"class": "sklearn.cross_decomposition.PLSRegression", "name": "n4probe_b4.not_called"}},
], ids=["class_step", "external_model_name", "nested_model_name"])
def test_b4_nirs4all_import_shaped_names_are_refused(make_catalog, step):
    recipe = {"pipeline": [step]}
    validate_recipe_structure(recipe, RecipeFormat.nirs4all_pipeline_config)
    root = make_catalog(recipe=recipe, descriptor_overrides={"governance": {"trust": "experimental"}})
    report = validate_pipeline(root, "demo_pipe")
    assert not report.errors
    assert any("n4probe_b4.not_called" in finding for finding in report.security_findings)
    for command in ("scan", "validate", "publish"):
        result = CliRunner().invoke(app, [command, "demo_pipe", "--root", str(root)])
        assert result.exit_code == 1, (command, result.output)
        assert "n4probe_b4.not_called" in result.output
    requirements = execution_requirements(recipe, Framework.nirs4all, RecipeFormat.nirs4all_pipeline_config)
    assert requirements["python_module_roots"] == ["sklearn"]
    assert "python_dependencies" in requirements["unknown"]


@pytest.mark.parametrize("failure", ["structure", "checksum"])
def test_strict_check_is_not_called_after_prior_errors(make_catalog, monkeypatch, failure):
    root = make_catalog(recipe={"pipeline": [{}]} if failure == "structure" else None)
    if failure == "checksum":
        build_catalog(root)
        (root / "pipelines/demo_pipe/card.md").write_text("Changed card\n")
    validation = importlib.import_module("nirs4all_repository.validate")
    monkeypatch.setattr(validation, "_strict_check", lambda *args: pytest.fail("strict checker reached an invalid bundle"))
    report = validation.validate_pipeline(root, "demo_pipe", strict=True)
    assert report.errors
    assert not report.ok
    result = CliRunner().invoke(app, ["validate", "demo_pipe", "--strict", "--root", str(root)])
    assert result.exit_code == 1
    assert "strict checker reached" not in str(result.exception)


@pytest.mark.parametrize("position", ["name", "func"])
def test_strict_rejection_prevents_marker_import_and_clean_input_calls_checker(make_catalog, monkeypatch, tmp_path, position):
    marker = tmp_path / "imported.txt"
    called = tmp_path / "called.txt"
    module_name = f"n4probe_b4_{position}"
    (tmp_path / f"{module_name}.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('imported')\n"
        f"def not_called():\n    Path({str(called)!r}).write_text('called')\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    step = {"class": "sklearn.preprocessing.FunctionTransformer"}
    if position == "name":
        step["name"] = f"{module_name}.not_called"
    else:
        step["params"] = {"func": f"{module_name}.not_called"}
    root = make_catalog(recipe={"pipeline": [step]})
    validation = importlib.import_module("nirs4all_repository.validate")
    calls = []

    def marker_strict_check(recipe, descriptor):
        calls.append(recipe)
        importlib.import_module(module_name)  # Benign module marker only; no callable is invoked.
        return ["safe stand-in strict check completed"]

    monkeypatch.setattr(validation, "_strict_check", marker_strict_check)
    report = validation.validate_pipeline(root, "demo_pipe", strict=True)
    assert report.security_findings
    assert calls == []
    assert not marker.exists()
    assert module_name not in sys.modules
    result = CliRunner().invoke(app, ["validate", "demo_pipe", "--strict", "--root", str(root)])
    assert result.exit_code == 1
    assert calls == []
    assert not marker.exists()

    # The guard must preserve opt-in strict checks on statically valid content.
    safe = {"pipeline": [{"class": "sklearn.preprocessing.FunctionTransformer", "name": "My step"}]}
    (root / "pipelines/demo_pipe/pipeline.json").write_text(json.dumps(safe))
    try:
        clean = validation.validate_pipeline(root, "demo_pipe", strict=True)
        assert clean.ok
        assert calls == [safe]
        assert clean.warnings == ["safe stand-in strict check completed"]
        assert marker.read_text() == "imported"
        assert not called.exists()
    finally:
        sys.modules.pop(module_name, None)


def test_pickle_scan_safe_payload():
    # A plain list of floats pickles to safe opcodes (no GLOBAL imports).
    result = scan_pickle_bytes(pickle.dumps([1.0, 2.0, 3.0]))
    assert result.ok, result.findings


def test_pickle_scan_flags_dangerous_global():
    payload = b"c__builtin__\neval\n(S'1+1'\ntR."
    result = scan_pickle_bytes(payload)
    assert not result.ok


def test_pickle_scan_flags_os_system():
    payload = b"cos\nsystem\n(S'echo hi'\ntR."
    result = scan_pickle_bytes(payload)
    assert not result.ok
    assert any("os" in f for f in result.findings)


def test_pickle_scan_flags_protocol4_stack_global():
    result = scan_pickle_bytes(_dangerous_pickle_payload())
    assert not result.ok
    assert any("system" in f for f in result.findings)


def test_validate_scans_inline_pickle_artifact(make_catalog):
    root = make_catalog("fitted_pickle")
    _attach_inline_artifact(root, "fitted_pickle", "artifacts/model.pkl", _dangerous_pickle_payload())

    report = validate_pipeline(root, "fitted_pickle")

    assert not report.ok
    assert any("artifacts/model.pkl" in finding for finding in report.security_findings)


def test_build_rejects_inline_pickle_artifact(make_catalog):
    root = make_catalog("fitted_pickle")
    _attach_inline_artifact(root, "fitted_pickle", "artifacts/model.pkl", _dangerous_pickle_payload())

    with pytest.raises(SecurityError):
        build_catalog(root)


def test_validate_scans_pickle_member_inside_n4a_zip(make_catalog):
    root = make_catalog("fitted_n4a")
    payload = _zip_with_pickle_member("model.pkl", _dangerous_pickle_payload())
    _attach_inline_artifact(root, "fitted_n4a", "artifacts/model.n4a", payload, backend="n4a")

    report = validate_pipeline(root, "fitted_n4a")

    assert not report.ok
    assert any("artifacts/model.n4a" in finding and "model.pkl" in finding for finding in report.security_findings)
