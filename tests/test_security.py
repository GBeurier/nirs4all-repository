# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Tests for the recipe class allow-list and the pickle-opcode scan."""

from __future__ import annotations

import hashlib
import io
import os
import pickle
import zipfile

import pytest
import yaml

from nirs4all_repository.builder import build_catalog
from nirs4all_repository.schema import RecipeFormat
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
