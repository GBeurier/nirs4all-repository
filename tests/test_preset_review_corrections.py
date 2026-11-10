"""Executed counterexamples for the Opus work review; no owner code is executed."""

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
from nirs4all_repository.bridge import BridgeError
from nirs4all_repository.builder import build_catalog
from nirs4all_repository.cli import app
from nirs4all_repository.recipes import RecipeError, execution_requirements
from nirs4all_repository.scaffold import scaffold_pipeline
from nirs4all_repository.schema import Framework, RecipeFormat
from nirs4all_repository.security import SecurityError, scan_config
from nirs4all_repository.site.presets import load_studio_presets
from nirs4all_repository.store import load_index
from nirs4all_repository.validate import validate_pipeline

ROOT = Path(__file__).resolve().parents[1]
FMT = RecipeFormat.nirs4all_pipeline_config
UNKNOWN = ["package_versions", "execution_profiles", "operations", "artifact_versions", "python_dependencies"]


def _text(value):
    # Type and mapping-order sensitive, unlike dict equality or a step fingerprint.
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


@pytest.fixture
def named_recipe():
    return {"name": "Order-sensitive synthetic recipe", "pipeline": [
        {"branch": {
            "z_first": ["sklearn.preprocessing.StandardScaler"],
            "a_second": [{"class": "sklearn.preprocessing.MinMaxScaler", "params": {"clip": True, "feature_range": [0, 1]}}],
        }},
        {"model": {"class": "sklearn.cross_decomposition.PLSRegression", "params": {"scale": False, "n_components": 2}}},
    ]}


def _sync_fixture(tmp_path, monkeypatch, recipe):
    spec = importlib.util.spec_from_file_location("review_sync", ROOT / "scripts/sync_studio_presets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "synthetic_source/api/presets/demo.yaml"
    source.parent.mkdir(parents=True)
    data = {"id": "demo", "name": "Synthetic order", "description": "Synthetic source only", "complexity": 1,
            "default_variant": "regression", "variants": {"regression": {"format": "yaml", **recipe}}}
    source.write_text(yaml.safe_dump(data, sort_keys=False))

    def fake_git(args, **kwargs):
        assert args == ["git", "-C", str(source.parents[2]), "rev-parse", "HEAD"]
        return "synthetic-revision\n"

    monkeypatch.setattr(module.subprocess, "check_output", fake_git)
    root = tmp_path / "destination"
    return module, source, root


def _cards(root):
    source = root / "catalog/studio-presets.json"
    (root / "catalog/studio-presets.cards.json").write_text(_text({
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "cards": {"demo": "synthetic fixture"},
    }))


@pytest.mark.parametrize("shape", ["pipeline", "steps", "list"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_scaffold_retains_nested_mapping_order_through_api_and_build(tmp_path, named_recipe, shape, newline):
    if shape == "steps":
        named_recipe["steps"] = named_recipe.pop("pipeline")
    elif shape == "list":
        named_recipe = named_recipe["pipeline"]
    source = tmp_path / "recipe.json"
    source.write_text(_text(named_recipe), encoding="utf-8", newline=newline)
    root = tmp_path / "destination"
    result = CliRunner().invoke(app, ["add", "ordered", "--recipe", str(source), "--root", str(root)])
    assert result.exit_code == 0, result.output
    build_catalog(root)
    pipe = n4r.get("ordered", root=root)
    assert _text(pipe.recipe()) == _text(named_recipe)
    assert (pipe.path / "pipeline.json").read_bytes() == _text(named_recipe).encode("utf-8")
    assert b"\r\n" not in (pipe.path / "descriptor.yaml").read_bytes()
    assert b"\r\n" not in (pipe.path / "card.md").read_bytes()
    assert _text(pipe.to_nirs4all()) == _text(named_recipe)


def test_sync_preserves_named_branch_order_recipe_bytes_and_snapshot_order(tmp_path, monkeypatch, named_recipe):
    module, source, root = _sync_fixture(tmp_path, monkeypatch, named_recipe)
    module.sync(source.parents[2], root)
    expected = {key: value for key, value in yaml.safe_load(source.read_text())["variants"]["regression"].items() if key != "format"}
    pipe = n4r.get("studio_demo_regression", root=root)
    from nirs4all_repository.store import load_descriptor_file

    assert load_descriptor_file(pipe.path / "descriptor.yaml") == pipe.descriptor
    assert (pipe.path / "pipeline.json").read_text() == _text(expected)
    assert b"\r\n" not in (pipe.path / "descriptor.yaml").read_bytes()
    assert b"\r\n" not in (pipe.path / "card.md").read_bytes()
    assert list(pipe.recipe()["pipeline"][0]["branch"]) == ["z_first", "a_second"]
    snapshot = root / "catalog/studio-presets.json"
    parsed = json.loads(snapshot.read_text())
    assert list(parsed) == ["source", "commit", "files_sha256", "presets"]
    assert list(parsed["presets"][0]["variants"]["regression"]["pipeline"][0]["branch"]) == ["z_first", "a_second"]
    assert _text(parsed["presets"][0]["variants"]["regression"]) == _text(yaml.safe_load(source.read_text())["variants"]["regression"])
    _cards(root)
    assert load_studio_presets(root, load_index(root)) is not None
    before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    module.sync(source.parents[2], root)
    assert before == {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_p09_current_twenty_snapshot_variants_reproduce_stored_bytes_without_sorting(repo_root):
    snapshot = json.loads((repo_root / "catalog/studio-presets.json").read_text())
    count = 0
    for preset in snapshot["presets"]:
        for task, pid in preset["repository_variants"].items():
            expected = {key: value for key, value in preset["variants"][task].items() if key != "format"}
            assert (repo_root / "pipelines" / pid / "pipeline.json").read_bytes() == _text(expected).encode()
            assert _text(n4r.get(pid, root=repo_root).recipe()) == _text(expected)
            count += 1
    assert count == 20


@pytest.mark.parametrize("reference,expected", [
    ({"class": "sklearn.preprocessing.StandardScaler"}, ["sklearn"]),
    ({"function": "numpy.mean"}, ["numpy"]),
    ({"instance": "sklearn.preprocessing.MinMaxScaler"}, ["sklearn"]),
    ("sklearn.preprocessing.StandardScaler", ["sklearn"]),
    ({"model": {"_or_": ["sklearn.linear_model.Ridge", {"function": "numpy.mean"}]}}, ["numpy", "sklearn"]),
    ({"branch": {"by_tag": "flag", "steps": {"true": ["sklearn.preprocessing.StandardScaler"], "false": [{"function": "numpy.mean"}]}}}, ["numpy", "sklearn"]),
])
def test_contextual_nirs4all_references_through_scaffold_requirements_and_remote(tmp_path, monkeypatch, reference, expected):
    recipe = {"pipeline": [reference], "provenance": {"version": "1.2", "source": "spectra.csv"}}
    source = tmp_path / "recipe.json"
    source.write_text(_text(recipe))
    root = tmp_path / "destination"
    scaffold_pipeline(root, "contexts", source)
    build_catalog(root)
    pipe = n4r.get("contexts", root=root)
    observed = pipe.execution_requirements()
    assert observed["python_module_roots"] == expected
    assert observed["unknown"] == UNKNOWN
    index = load_index(root)
    assert n4r.list(root=root)[0]["execution_requirements"] == observed
    assert json.loads((pipe.path / "manifest.json").read_text())["execution_requirements"] == observed
    transport = importlib.import_module("nirs4all_repository.fetch")

    def fake_http(url, **kwargs):
        if url.endswith("index.json"):
            return _text(index).encode()
        return (pipe.path / url.rsplit("/", 1)[-1]).read_bytes()

    monkeypatch.setattr(transport, "http_get", fake_http)
    monkeypatch.setattr(n4r, "_catalog_root", lambda *args: None)
    monkeypatch.setattr(n4r, "bundled_root", lambda: None)
    downloaded = n4r.get("contexts", cache_dir=tmp_path / "cache")
    assert not (downloaded.path / "manifest.json").exists()
    assert _text(downloaded.recipe()) == _text(recipe)
    assert downloaded.execution_requirements() == observed


@pytest.mark.parametrize("fmt,recipe,expected", [
    ("dag-ml/pipeline-dsl", {"id": "branch.input", "steps": [
        {"kind": "transform", "id": "aug.0", "operator": "sklearn.preprocessing.StandardScaler", "params": {"filename": "data/spectra.csv"}},
        {"kind": "model", "id": "branch.x", "operator": {"function": "numpy.mean"}},
    ]}, ["numpy", "sklearn"]),
    ("dag-ml/pipeline-dsl", {"steps": [{"kind": "model", "id": "branch.x", "operator": {"ref": "sklearn.linear_model.Ridge"}}]}, ["sklearn"]),
    ("dag-ml/pipeline-dsl", {"steps": [{"kind": "transform", "id": "aug.0", "operator": {"type": "sklearn.preprocessing.StandardScaler"}}]}, ["sklearn"]),
    ("dag-ml/compiled-artifact", {"graph": {"id": "branch.x", "nodes": [
        {"id": "aug.0", "kind": "transform", "operator": {"callable": "numpy.mean"}},
    ]}, "campaign_template": {}}, ["numpy"]),
    ("dag-ml/pipeline-dsl", {"steps": [{"kind": "model", "id": "branch.x", "operator": {"type": "PLS"}}]}, []),
])
def test_dagml_operator_and_callable_descriptor_contexts(make_catalog, fmt, recipe, expected):
    root = make_catalog(recipe=recipe, framework="dag-ml", descriptor_overrides={"recipe": {"format": fmt, "path": "pipeline.json"}})
    build_catalog(root)
    pipe = n4r.get("demo_pipe", root=root)
    assert _text(pipe.to_dagml()) == _text(recipe)
    assert pipe.execution_requirements()["python_module_roots"] == expected
    assert pipe.execution_requirements()["unknown"] == UNKNOWN
    assert n4r.list(root=root)[0]["execution_requirements"] == pipe.execution_requirements()


def test_contextual_requirements_do_not_limit_conservative_security(make_catalog):
    recipe = {"name": "xgboost.sweep", "provenance": {"version": "1.2", "source": "spectra.csv", "label": "v1.2"}, "pipeline": [
        {"class": "sklearn.preprocessing.StandardScaler", "name": "xgboost.sweep", "params": {
            "filename": "spectra.csv", "version": "1.2.3", "threshold_label": "0.5", "description": "os.system",
            "ordinary": ["catboost.data", "1.2", "sklearn.not_a_reference"],
            "choices": {"_or_": ["a.b", "c.d"]},
        }},
    ]}
    root = make_catalog(recipe=recipe)
    block = execution_requirements(recipe, Framework.nirs4all, FMT)
    assert block["python_module_roots"] == ["sklearn"]
    assert block["unknown"] == UNKNOWN
    assert not validate_pipeline(root, "demo_pipe").ok
    assert not scan_config(recipe, FMT).ok
    with pytest.raises(SecurityError, match="os.system"):
        build_catalog(root)
    assert _text(json.loads((root / "pipelines/demo_pipe/pipeline.json").read_text())) == _text(recipe)


def test_actual_model_factory_dependencies_remain_explicitly_unknown(repo_root):
    ids = [entry["id"] for entry in n4r.list(root=repo_root) if "nonlinear_exploration" in entry["id"]]
    assert len(ids) == 4
    for pid in ids:
        pipe = n4r.get(pid, root=repo_root)
        assert '"framework": "pytorch"' in _text(pipe.recipe())
        block = pipe.execution_requirements()
        assert "nirs4all" in block["python_module_roots"]
        assert "torch" not in block["python_module_roots"]
        assert block["unknown"] == UNKNOWN


@pytest.mark.parametrize("reference", ["n4m:pls", "n4m.SNV"])
def test_native_namespace_remains_unqualified_and_is_not_a_python_dependency(make_catalog, reference):
    recipe = {"pipeline": [{"model": reference}]}
    block = execution_requirements(recipe, Framework.nirs4all, FMT)
    assert block["python_module_roots"] == []
    assert block["unknown"] == UNKNOWN
    scan = scan_config(recipe, FMT)
    assert not scan.ok
    assert "unqualified owner namespace" in scan.findings[0]
    root = make_catalog(recipe=recipe)
    with pytest.raises(SecurityError, match="n4m"):
        build_catalog(root)


@pytest.mark.parametrize("field", ["class", "function", "instance", "enum"])
@pytest.mark.parametrize("location", ["provenance", "params", "name", "target"])
def test_explicit_references_cannot_hide_in_data_or_metadata(make_catalog, field, location):
    recipe = {"pipeline": [{"class": "sklearn.preprocessing.StandardScaler"}], location: {"nested": [{field: "os.system"}]}}
    if location == "params":
        recipe["pipeline"][0]["params"] = recipe.pop("params")
    root = make_catalog(recipe=recipe)
    block = execution_requirements(recipe, Framework.nirs4all, FMT)
    assert "os" in block["python_module_roots"]
    report = validate_pipeline(root, "demo_pipe")
    assert not report.ok
    assert any("os.system" in finding for finding in report.security_findings)
    with pytest.raises(SecurityError, match="os.system"):
        build_catalog(root)


@pytest.mark.parametrize("operator", ["os.system", {"ref": "os.system"}, {"type": "os.system"}, {"callable": "os.system"}])
def test_opaque_dagml_operator_references_still_reach_security_scan(make_catalog, operator):
    recipe = {"steps": [{"kind": "transform", "id": "safe.id", "operator": operator}]}
    root = make_catalog(framework="dag-ml", recipe=recipe)
    with pytest.raises(SecurityError, match="os.system"):
        build_catalog(root)


def test_bare_references_inside_named_separation_steps_are_scanned(make_catalog):
    recipe = {"pipeline": [{"branch": {"by_tag": "flag", "steps": {"true": ["os.system"], "false": ["sklearn.preprocessing.StandardScaler"]}}}]}
    root = make_catalog(recipe=recipe)
    with pytest.raises(SecurityError, match="os.system"):
        build_catalog(root)


@pytest.mark.parametrize("duplicate", [
    'id: demo\nid: replaced\n',
    'variants:\n  regression:\n    pipeline: ["sklearn.linear_model.Ridge"]\n    pipeline: ["sklearn.linear_model.Lasso"]\n',
    'variants:\n  regression:\n    pipeline:\n      - class: sklearn.linear_model.Ridge\n        params: {alpha: 1, alpha: 2}\n',
])
def test_duplicate_yaml_source_is_refused_before_writes_or_git(tmp_path, monkeypatch, named_recipe, duplicate):
    module, source, root = _sync_fixture(tmp_path, monkeypatch, named_recipe)
    source.write_text(duplicate)
    monkeypatch.setattr(module.subprocess, "check_output", lambda *args, **kwargs: pytest.fail("duplicate YAML reached source git"))
    with pytest.raises(RecipeError, match="duplicate YAML"):
        module.sync(source.parents[2], root)
    assert not root.exists()


@pytest.mark.parametrize("mutation", ["bool_to_int", "branch_order", "missing_mapping", "unmapped_variant"])
def test_site_parity_refuses_type_order_and_variant_coverage_changes(tmp_path, monkeypatch, named_recipe, mutation):
    module, source, root = _sync_fixture(tmp_path, monkeypatch, named_recipe)
    module.sync(source.parents[2], root)
    _cards(root)
    assert load_studio_presets(root, load_index(root)) is not None
    if mutation in {"bool_to_int", "branch_order"}:
        path = root / "pipelines/studio_demo_regression/pipeline.json"
        recipe = json.loads(path.read_text())
        branch = recipe["pipeline"][0]["branch"]
        if mutation == "bool_to_int":
            branch["a_second"][0]["params"]["clip"] = 1
        else:
            recipe["pipeline"][0]["branch"] = dict(reversed(list(branch.items())))
        assert recipe == named_recipe  # Deliberate counterexample to ordinary equality.
        path.write_text(_text(recipe))
        expected = "differs from snapshot"
    else:
        path = root / "catalog/studio-presets.json"
        snapshot = json.loads(path.read_text())
        preset = snapshot["presets"][0]
        if mutation == "missing_mapping":
            preset.pop("repository_variants")
        else:
            preset["variants"]["classification"] = copy.deepcopy(preset["variants"]["regression"])
        path.write_text(_text(snapshot))
        _cards(root)  # Avoid testing only the pre-existing checksum gate.
        expected = "mapping is incomplete"
    with pytest.raises(ValueError, match=expected):
        load_studio_presets(root, load_index(root))


@pytest.mark.parametrize("suffix", [".yaml", ".yml", ".txt", ""])
def test_non_json_suffix_is_refused_even_with_valid_json_content(tmp_path, named_recipe, suffix):
    source = tmp_path / ("source" + suffix)
    source.write_text(_text(named_recipe))
    with pytest.raises(RecipeError, match=".json"):
        scaffold_pipeline(tmp_path / "destination", "valid_tree", source)
    assert not (tmp_path / "destination").exists()


@pytest.mark.parametrize("mutation", ["schema", "status", "unknown_coverage", "numeric_root", "framework", "null"])
def test_malformed_requirements_are_rejected_by_local_remote_and_materializer(make_catalog, monkeypatch, tmp_path, mutation):
    root = make_catalog()
    build_catalog(root)
    index = load_index(root)
    entry = index["pipelines"]["demo_pipe"]
    block = entry["execution_requirements"]
    if mutation == "schema":
        block["schema"] = "x.v99"
    elif mutation == "status":
        block["status"] = "supported"
    elif mutation == "unknown_coverage":
        block["unknown"].remove("python_dependencies")
    elif mutation == "numeric_root":
        block["python_module_roots"] = ["1"]
    elif mutation == "framework":
        block["framework"] = "dag-ml"
    else:
        entry["execution_requirements"] = None
    (root / "catalog/index.json").write_text(_text(index))
    with pytest.raises(ValueError):
        load_index(root)
    with pytest.raises(ValueError):
        n4r.list(root=root)
    transport = importlib.import_module("nirs4all_repository.fetch")
    monkeypatch.setattr(transport, "http_get", lambda *args, **kwargs: _text(index).encode())
    with pytest.raises(ValueError):
        transport.fetch_index("https://synthetic.invalid")
    monkeypatch.setattr(transport, "http_get", lambda *args, **kwargs: pytest.fail("malformed observations triggered a download"))
    with pytest.raises(ValueError):
        transport.materialize_remote(entry, tmp_path / "cache")
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize("mutation", ["schema", "status", "coverage", "observations"])
def test_manifest_version_and_requirements_tampering_fail_validation(make_catalog, mutation):
    root = make_catalog()
    build_catalog(root)
    path = root / "pipelines/demo_pipe/manifest.json"
    manifest = json.loads(path.read_text())
    if mutation == "schema":
        manifest["schema_version"] = 99
    elif mutation == "status":
        manifest["execution_requirements"]["status"] = "supported"
    elif mutation == "coverage":
        manifest["execution_requirements"]["unknown"] = UNKNOWN[:-1]
    else:
        manifest["execution_requirements"]["python_module_roots"] = ["numpy"]
    path.write_text(_text(manifest))
    report = validate_pipeline(root, "demo_pipe")
    assert not report.ok
    assert any("manifest invalid" in error for error in report.errors)
    with pytest.raises(BridgeError, match="manifest invalid"):
        n4r.get("demo_pipe", root=root)
    assert CliRunner().invoke(app, ["validate", "--all", "--root", str(root)]).exit_code == 1


@pytest.mark.parametrize("mutation", ["schema", "status"])
def test_publish_readiness_uses_manifest_and_requirements_validation(make_catalog, mutation):
    root = make_catalog(descriptor_overrides={"governance": {"status": "draft", "visibility": "public", "trust": "experimental"}})
    build_catalog(root)
    assert CliRunner().invoke(app, ["publish", "demo_pipe", "--root", str(root)]).exit_code == 0
    path = root / "pipelines/demo_pipe/manifest.json"
    manifest = json.loads(path.read_text())
    if mutation == "schema":
        manifest["schema_version"] = 99
    else:
        manifest["execution_requirements"]["status"] = "supported"
    path.write_text(_text(manifest))
    result = CliRunner().invoke(app, ["publish", "demo_pipe", "--root", str(root)])
    assert result.exit_code == 1
    assert "manifest invalid" in result.output
    assert "ready to publish" not in result.output


def test_missing_old_metadata_stays_unqualified_and_remote_claims_are_recomputed(make_catalog, monkeypatch, tmp_path):
    root = make_catalog()
    build_catalog(root)
    index = load_index(root)
    entry = index["pipelines"]["demo_pipe"]
    entry.pop("execution_requirements")
    (root / "catalog/index.json").write_text(_text(index))
    assert "execution_requirements" not in n4r.list(root=root)[0]
    transport = importlib.import_module("nirs4all_repository.fetch")
    bundle = root / "pipelines/demo_pipe"
    monkeypatch.setattr(transport, "http_get", lambda url, **kwargs: (bundle / url.rsplit("/", 1)[-1]).read_bytes())
    downloaded = transport.materialize_remote(entry, tmp_path / "old_cache")
    assert not (downloaded / "manifest.json").exists()
    observed = n4r.get("demo_pipe", root=root).execution_requirements()
    assert observed["unknown"] == UNKNOWN
    entry["execution_requirements"] = copy.deepcopy(observed)
    entry["execution_requirements"]["python_module_roots"] = ["numpy"]
    with pytest.raises(transport.FetchError, match="differs from index execution requirements"):
        transport.materialize_remote(entry, tmp_path / "cache")
