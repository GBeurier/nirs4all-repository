"""Production-path preservation and refusal probes; synthetic data, no execution claims."""

from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

import nirs4all_repository as n4r
from nirs4all_repository.bridge import BridgeError, Pipeline
from nirs4all_repository.builder import build_catalog
from nirs4all_repository.canonical import canonical_json
from nirs4all_repository.cli import app
from nirs4all_repository.recipes import RecipeError, load_recipe_text, recipe_fingerprints, validate_recipe_structure
from nirs4all_repository.scaffold import scaffold_pipeline
from nirs4all_repository.schema import RecipeFormat, SchemaVersionError
from nirs4all_repository.security import SecurityError, scan_config
from nirs4all_repository.site.presets import load_studio_presets
from nirs4all_repository.store import load_descriptor, load_index
from nirs4all_repository.validate import validate_pipeline

FMT = RecipeFormat.nirs4all_pipeline_config
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def full_recipe():
    # Synthetic B02 counterexample, not a claim about existing catalog SNV settings.
    return {
        "name": "v1.2", "description": "A complete synthetic recipe.", "random_state": 19,
        "steps": [
            {"branch": [
                [{"class": "nirs4all.operators.transforms.StandardNormalVariate", "params": {"with_std": False}}],
                [{"_or_": [
                    {"class": "sklearn.preprocessing.StandardScaler", "params": {"with_std": False}},
                    {"class": "sklearn.preprocessing.MinMaxScaler"},
                ], "count": 1}],
            ]},
            {"y_processing": {"class": "sklearn.preprocessing.StandardScaler"}},
            {"class": "sklearn.model_selection.KFold", "params": {"n_splits": 3, "shuffle": True, "random_state": 19}},
            {"model": {"class": "sklearn.cross_decomposition.PLSRegression", "params": {"scale": False, "n_components": 2}},
             "finetune_params": {"n_components": {"_range_": [1, 4]}}, "train_params": {"sample_weight": [1, 2]}},
        ],
        "search": {"_cartesian_": [{"n_components": [1, 2]}, {"scale": [False]}], "folds": {"ids": ["fold_a", "fold_b"]}},
        "target": {"name": "protein", "columns": [1], "mask": [True, False]},
        "provenance": {"source": "synthetic B02 regression", "seed": 19},
        "sources": [{"id": "nir", "columns": [0, 3], "sample_ids": ["a", "b"]}],
        "choice": {"selected": 0, "alternatives": [None, False, {"params": {"scale": False}}]},
    }


@pytest.mark.parametrize("shape", ["steps", "pipeline", "list"])
def test_complete_tree_through_scaffold_build_api_and_export(tmp_path, full_recipe, shape):
    recipe = copy.deepcopy(full_recipe)
    if shape == "pipeline":
        recipe["pipeline"] = recipe.pop("steps")
    elif shape == "list":
        recipe = recipe["steps"]
    original = copy.deepcopy(recipe)
    source = tmp_path / "input.json"
    source.write_text(json.dumps(recipe))
    root = tmp_path / "catalogue"
    result = CliRunner().invoke(app, ["add", "complete_tree", "--recipe", str(source), "--root", str(root)])
    assert result.exit_code == 0, result.output
    build_catalog(root)
    assert validate_pipeline(root, "complete_tree").ok
    pipe = n4r.get_pipeline("complete_tree", root=root)
    assert pipe.recipe() == original
    assert json.loads((pipe.path / "pipeline.json").read_text()) == original
    assert n4r.get_bundle("complete_tree", root=root) == pipe.path
    if shape == "list":
        assert pipe.to_nirs4all() == original
    else:
        with pytest.raises(BridgeError, match="root fields would be lost"):
            pipe.to_nirs4all()
    assert recipe == original
    # Export data through the real remote materializer with transport replaced.
    transport = importlib.import_module("nirs4all_repository.fetch")
    entry = n4r.get_pipeline_list(root=root)[0]
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(transport, "http_get", lambda url, **_: (pipe.path / url.rsplit("/", 1)[-1]).read_bytes())
        remote = transport.materialize_remote(entry, tmp_path / "cache")
    assert not (remote / "manifest.json").exists()
    resolved = Pipeline(load_descriptor(root, "complete_tree"), remote)
    assert resolved.recipe() == original
    expected = pipe.execution_requirements()
    assert resolved.execution_requirements() == expected
    assert entry["execution_requirements"] == expected
    assert json.loads((pipe.path / "manifest.json").read_text())["execution_requirements"] == expected
    # Returning mutable parsed data must not change the stored tree.
    returned = pipe.recipe()
    if isinstance(returned, dict):
        returned.clear()
    assert pipe.recipe() == original


@pytest.mark.parametrize("alias", ["pipeline", "steps"])
def test_bridge_accepts_only_documented_root_fields(make_catalog, alias):
    recipe = {alias: [{"model": {"class": "sklearn.linear_model.Ridge"}}], "name": "v1.2", "description": "x.y", "random_state": 42}
    root = make_catalog(recipe=recipe)
    build_catalog(root)
    assert n4r.get("demo_pipe", root=root).to_nirs4all() == recipe


@pytest.mark.parametrize("key", ["search", "target", "provenance", "sources", "choice", "future_field"])
def test_bridge_refuses_every_unrecognized_root_field(make_catalog, key):
    recipe = {"pipeline": [{"class": "sklearn.linear_model.Ridge"}], key: {"keep": False}}
    root = make_catalog(recipe=recipe)
    build_catalog(root)
    pipe = n4r.get("demo_pipe", root=root)
    assert pipe.recipe() == recipe
    with pytest.raises(BridgeError, match=key):
        pipe.to_nirs4all()


def test_alias_conflict_refused_at_all_admission_paths(make_catalog, tmp_path):
    recipe = {"pipeline": [{"class": "sklearn.linear_model.Ridge"}], "steps": [{"class": "os.system"}]}
    root = make_catalog(recipe=recipe)
    report = validate_pipeline(root, "demo_pipe")
    assert not report.ok
    assert any("exactly one" in item for item in report.errors)
    assert any("os.system" in item for item in report.security_findings)
    with pytest.raises(RecipeError, match="exactly one"):
        build_catalog(root)
    with pytest.raises(RecipeError, match="exactly one"):
        scaffold_pipeline(tmp_path / "new", "conflict", root / "pipelines/demo_pipe/pipeline.json")
    assert not (tmp_path / "new").exists()
    with pytest.raises(RecipeError, match="exactly one"):
        n4r.get("demo_pipe", root=root).recipe()


@pytest.mark.parametrize("location", ["target", "search", "provenance", "sources", "name", "description"])
def test_security_scan_covers_root_and_nested_fields(make_catalog, location):
    recipe = {"pipeline": [{"class": "sklearn.linear_model.Ridge"}], location: {"nested": [{"class": "os.system"}]}}
    root = make_catalog(recipe=recipe)
    report = validate_pipeline(root, "demo_pipe")
    assert not report.ok
    assert any("os.system" in item for item in report.security_findings)
    with pytest.raises(SecurityError, match="os.system"):
        build_catalog(root)


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan"), {True: "branch"}, {1: "branch"}, (1, 2)])
def test_non_json_values_refused_without_coercion(bad):
    recipe = {"pipeline": [{"class": "sklearn.linear_model.Ridge"}], "choice": bad}
    with pytest.raises(RecipeError, match="strict JSON"):
        validate_recipe_structure(recipe, FMT)
    with pytest.raises((ValueError, TypeError)):
        canonical_json(recipe)


@pytest.mark.parametrize("text,extension", [
    ('{"pipeline":[{"class":"sklearn.linear_model.Ridge","params":{"alpha":Infinity}}]}', ".json"),
    ('{"pipeline":[{"class":"sklearn.linear_model.Ridge"}],"x":1e999}', ".json"),
    ('{"pipeline":[{"class":"sklearn.linear_model.Ridge"}],"choice":NaN}', ".json"),
    ('{"pipeline":[{"class":"sklearn.linear_model.Ridge"}],"choice":1,"choice":2}', ".json"),
    ('pipeline: [{class: sklearn.linear_model.Ridge}]\nchoice: {true: a, false: b}', ".yaml"),
    ('pipeline: [{class: sklearn.linear_model.Ridge}]', ".json"),
])
def test_strict_file_refusal_in_validate_scaffold_and_build(make_catalog, tmp_path, text, extension):
    root = make_catalog(descriptor_overrides={"recipe": {"format": FMT.value, "path": "pipeline" + extension}})
    source = root / "pipelines/demo_pipe" / ("pipeline" + extension)
    source.write_text(text)
    report = validate_pipeline(root, "demo_pipe")
    assert not report.ok
    assert "recipe could not be parsed" in report.errors[0]
    with pytest.raises(RecipeError):
        scaffold_pipeline(tmp_path / "new", "invalid", source)
    assert not (tmp_path / "new").exists()
    with pytest.raises(RecipeError):
        build_catalog(root)


@pytest.mark.parametrize("version", [None, 0, 99, "1", True])
def test_local_and_remote_index_versions_refused(tmp_path, monkeypatch, version):
    path = tmp_path / "catalog/index.json"
    path.parent.mkdir()
    data = {"schema_version": version, "pipelines": {}}
    path.write_text(json.dumps(data))
    with pytest.raises(SchemaVersionError):
        load_index(tmp_path)
    transport = importlib.import_module("nirs4all_repository.fetch")
    monkeypatch.setattr(transport, "http_get", lambda *_, **__: path.read_bytes())
    with pytest.raises(SchemaVersionError):
        transport.fetch_index("https://synthetic.invalid")
    data["schema_version"] = 1
    path.write_text(json.dumps(data))
    assert load_index(tmp_path) == data
    assert transport.fetch_index("https://synthetic.invalid") == data


def _sync_module():
    spec = importlib.util.spec_from_file_location("sync_presets", ROOT / "scripts/sync_studio_presets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _synthetic_source(tmp_path, recipe):
    source_root = tmp_path / "synthetic_source"
    source = source_root / "api/presets/demo.yaml"
    source.parent.mkdir(parents=True)
    data = {"id": "demo", "name": "Synthetic", "description": "Synthetic import probe", "default_variant": "regression",
            "complexity": 1, "variants": {"regression": {"format": "yaml", **recipe}}}
    source.write_text(yaml.safe_dump(data, sort_keys=False))
    return source_root, source


def test_synthetic_sync_and_whole_variant_parity(tmp_path, monkeypatch, full_recipe):
    source_root, source = _synthetic_source(tmp_path, full_recipe)
    module = _sync_module()
    calls = []

    def fake_git(args, **kwargs):
        calls.append(args)
        assert args == ["git", "-C", str(source_root), "rev-parse", "HEAD"]
        return "synthetic-source-revision\n"

    monkeypatch.setattr(module.subprocess, "check_output", fake_git)
    root = tmp_path / "destination"
    module.sync(source_root, root)
    assert len(calls) == 1
    pipe = n4r.get("studio_demo_regression", root=root)
    assert pipe.recipe() == full_recipe
    snapshot = root / "catalog/studio-presets.json"
    data = json.loads(snapshot.read_text())
    assert data["commit"] == "synthetic-source-revision"
    assert data["files_sha256"] == {"demo.yaml": hashlib.sha256(source.read_bytes()).hexdigest()}
    # Minimal synthetic card evidence: no frontend renderer or real Studio source.
    (root / "catalog/studio-presets.cards.json").write_text(json.dumps({
        "source_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(), "cards": {"demo": "synthetic"}}))
    assert load_studio_presets(root, load_index(root)) is not None
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    module.sync(source_root, root)
    assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    for key in ("target", "search", "choice", "provenance", "sources"):
        altered = copy.deepcopy(full_recipe)
        altered.pop(key)
        (pipe.path / "pipeline.json").write_text(json.dumps(altered))
        with pytest.raises(ValueError, match="differs from snapshot"):
            load_studio_presets(root, load_index(root))
    # A shape rewrite must also be detected, without a KeyError.
    altered = copy.deepcopy(full_recipe)
    altered["pipeline"] = altered.pop("steps")
    (pipe.path / "pipeline.json").write_text(json.dumps(altered))
    with pytest.raises(ValueError, match="differs from snapshot"):
        load_studio_presets(root, load_index(root))


@pytest.mark.parametrize("invalid", [
    {"pipeline": [{"class": "sklearn.linear_model.Ridge"}], "steps": [{"class": "sklearn.linear_model.Ridge"}]},
    {"pipeline": [{"class": "sklearn.linear_model.Ridge", "params": {"by_tag": {True: 1}}}]},
    {"pipeline": [{"class": "sklearn.linear_model.Ridge", "params": {"alpha": float("inf")}}]},
    {"pipeline": [{"class": "sklearn.linear_model.Ridge"}], "search": {"class": "os.system"}},
])
def test_synthetic_sync_refuses_before_writing(tmp_path, monkeypatch, invalid):
    source_root, _ = _synthetic_source(tmp_path, invalid)
    module = _sync_module()
    monkeypatch.setattr(module.subprocess, "check_output", lambda *_, **__: pytest.fail("invalid source reached git"))
    target = tmp_path / "destination"
    with pytest.raises((ValueError, SecurityError)):
        module.sync(source_root, target)
    assert not target.exists()


def test_actual_catalog_complete_trees_and_requirements(repo_root, monkeypatch):
    # Reproduce a legacy Windows locale while honoring explicit UTF-8 reads.
    read_text = Path.read_text

    def windows_read_text(path, encoding=None, errors=None):
        return read_text(path, encoding=encoding or "cp1252", errors=errors)

    monkeypatch.setattr(Path, "read_text", windows_read_text)
    entries = n4r.get_pipeline_list(root=repo_root)
    assert len(entries) == 26
    snapshot = json.loads((repo_root / "catalog/studio-presets.json").read_text(encoding="utf-8"))
    imported = {pid: {key: value for key, value in preset["variants"][task].items() if key != "format"}
                for preset in snapshot["presets"] for task, pid in preset["repository_variants"].items()}
    assert len(imported) == 20
    contract = json.loads((repo_root / "contracts/execution-requirements.v1.schema.json").read_text(encoding="utf-8"))
    for entry in entries:
        pipe = n4r.get_pipeline(entry["id"], root=repo_root)
        raw = json.loads((pipe.path / pipe.descriptor.recipe.path).read_text(encoding="utf-8"))
        assert pipe.recipe() == raw
        assert scan_config(raw, pipe.descriptor.recipe.format).ok
        assert validate_pipeline(repo_root, pipe.id).ok
        if pipe.id in imported:
            assert raw == imported[pipe.id]
        requirements = pipe.execution_requirements()
        assert set(requirements) == set(contract["required"]) == set(contract["properties"])
        for key, field in contract["properties"].items():
            if "const" in field:
                assert requirements[key] == field["const"]
            if "enum" in field:
                assert requirements[key] in field["enum"]
        assert requirements["python_module_roots"] == sorted(set(requirements["python_module_roots"]))
        assert requirements == entry["execution_requirements"]
        assert requirements == json.loads((pipe.path / "manifest.json").read_text(encoding="utf-8"))["execution_requirements"]
        assert requirements["framework"] == pipe.descriptor.framework.value
        assert requirements["recipe_format"] == n4r.card(pipe.id, root=repo_root)["recipe"]["format"]
        assert requirements["unknown"] == ["package_versions", "execution_profiles", "operations", "artifact_versions", "python_dependencies"]
        assert "supported" not in json.dumps(requirements)
        assert "unsupported" not in json.dumps(requirements)
        assert "execution_requirements" not in n4r.card(pipe.id, root=repo_root)
        if pipe.descriptor.framework.value == "nirs4all":
            assert pipe.to_nirs4all() == raw
        else:
            assert pipe.to_dagml() == raw


def test_requirements_are_observations_not_user_execution_claims(make_catalog, full_recipe):
    root = make_catalog(recipe=full_recipe)
    build_catalog(root)
    pipe = n4r.get("demo_pipe", root=root)
    assert pipe.execution_requirements() == {
        "schema": "nirs4all-repository.execution-requirements.v1", "framework": "nirs4all", "recipe_format": FMT.value,
        "python_module_roots": ["nirs4all", "sklearn"],
        "unknown": ["package_versions", "execution_profiles", "operations", "artifact_versions", "python_dependencies"],
    }
    # A descriptor cannot smuggle an unsupported/new qualification contract into v1.
    descriptor = pipe.path / "descriptor.yaml"
    data = yaml.safe_load(descriptor.read_text())
    data["execution_requirements"] = {"execution_profiles": ["native-workflow@1"], "supported": True}
    descriptor.write_text(yaml.safe_dump(data))
    report = validate_pipeline(root, "demo_pipe")
    assert not report.ok
    assert "Extra inputs are not permitted" in report.errors[0]


def test_recipe_claims_cannot_override_derived_unknowns(make_catalog, full_recipe):
    full_recipe["execution_requirements"] = {"execution_profiles": ["native-workflow@1"], "operations": ["fit"], "supported": True}
    root = make_catalog(recipe=full_recipe)
    build_catalog(root)
    pipe = n4r.get("demo_pipe", root=root)
    assert pipe.recipe() == full_recipe
    requirements = pipe.execution_requirements()
    assert "execution_profiles" not in requirements
    assert "operations" not in requirements
    assert "supported" not in requirements
    assert requirements == n4r.list(root=root)[0]["execution_requirements"]
    assert requirements["unknown"] == ["package_versions", "execution_profiles", "operations", "artifact_versions", "python_dependencies"]
    with pytest.raises(BridgeError, match="execution_requirements"):
        pipe.to_nirs4all()


@pytest.mark.parametrize("fmt,recipe", [
    ("dag-ml/pipeline-dsl", [{"class": "nirs4all.operators.transforms.StandardNormalVariate", "params": {"with_std": False}}]),
    ("dag-ml/compiled-artifact", {"graph": {"nodes": []}, "campaign_template": {}, "provenance": {"source": "synthetic"}}),
])
def test_dagml_formats_preserve_content_and_do_not_infer_requirements(make_catalog, fmt, recipe):
    root = make_catalog(framework="dag-ml", recipe=recipe, descriptor_overrides={"recipe": {"format": fmt, "path": "pipeline.json"}})
    build_catalog(root)
    pipe = n4r.get("demo_pipe", root=root)
    assert pipe.to_dagml() == recipe
    requirements = pipe.execution_requirements()
    assert requirements["framework"] == "dag-ml"
    assert requirements["recipe_format"] == fmt
    assert requirements["unknown"] == ["package_versions", "execution_profiles", "operations", "artifact_versions", "python_dependencies"]
    assert requirements == n4r.list(root=root)[0]["execution_requirements"]
    with pytest.raises(BridgeError, match="not nirs4all"):
        pipe.to_nirs4all()


def test_json_parser_refuses_duplicate_keys_at_any_depth():
    with pytest.raises(RecipeError, match="duplicate"):
        load_recipe_text('{"pipeline":[{"class":"sklearn.linear_model.Ridge","params":{"alpha":1,"alpha":2}}]}')


def test_legacy_step_fingerprint_does_not_identify_root_content(full_recipe):
    changed = copy.deepcopy(full_recipe)
    changed["search"]["folds"]["ids"] = ["other_fold"]
    changed["target"]["name"] = "other_target"
    assert recipe_fingerprints(changed, FMT) == recipe_fingerprints(full_recipe, FMT)
    assert hashlib.sha256(canonical_json(changed).encode()).hexdigest() != hashlib.sha256(canonical_json(full_recipe).encode()).hexdigest()
