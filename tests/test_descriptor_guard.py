# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Owner file/bytes/remote entry points share the bounded descriptor parser."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

import nirs4all_repository as repository
from nirs4all_repository.builder import build_catalog
from nirs4all_repository.schema import PipelineDescriptor
from nirs4all_repository.store import DescriptorSyntaxError, load_descriptor_bytes, load_descriptor_file, parse_descriptor_bytes
from nirs4all_repository.validate import validate_all, validate_pipeline

REFUSALS = [
    ("descriptor_too_large", b"x" * ((1 << 20) + 1)),
    ("descriptor_not_utf8", b"\xff"),
    ("descriptor_yaml_invalid", b"x: ["),
    ("descriptor_alias_refused", b"x: &a [1]\ny: *a\n"),
    ("descriptor_merge_refused", b"x: {<<: {status: published}, status: draft}"),
    ("descriptor_explicit_tag_refused", b"x: !!str 5"),
    ("descriptor_duplicate_key", b"governance: {status: published}\ngovernance: {status: draft}"),
    ("descriptor_too_deep", b"[" * 33 + b"0" + b"]" * 33),
    ("descriptor_too_many_events", b"[" + b"0," * 20000 + b"0]"),
    ("descriptor_sexagesimal_refused", b"x: 1:30.5"),
    ("descriptor_nonfinite", b"x: 1.0e+999"),
    ("descriptor_invalid_unicode", b'x: "\\ud800"'),
]


@pytest.mark.parametrize("code,raw", REFUSALS)
def test_owner_file_bytes_remote_and_validation_refuse(tmp_path, monkeypatch, code, raw):
    sentinel = b"\n# PRIVATE_INPUT_SENTINEL\n"
    raw += sentinel
    path = tmp_path / "pipelines" / "remote" / "descriptor.yaml"
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    monkeypatch.setattr(repository, "_catalog_root", lambda *a: None)
    monkeypatch.setattr(repository, "bundled_root", lambda: None)
    monkeypatch.setattr(repository, "_load_index_any", lambda *a: {"pipelines": {"remote": {"descriptor": {"url": "synthetic"}}}})
    monkeypatch.setattr(repository._fetch_module, "fetch_verified", lambda *a: raw)
    for call in (lambda: load_descriptor_bytes(raw), lambda: load_descriptor_file(path), lambda: repository.card("remote")):
        with pytest.raises(DescriptorSyntaxError) as error:
            call()
        assert error.value.code == code
        assert str(error.value) == code
        assert error.value.__suppress_context__ or error.value.__context__ is None
    report = validate_pipeline(tmp_path, "remote")
    assert not report.ok
    assert report.errors == ["descriptor invalid: " + code]


@pytest.mark.parametrize("raw,code", [
    (b"x: {<<: [{status: published}]}", "descriptor_merge_refused"),
    (b"x: !!binary aGk=", "descriptor_explicit_tag_refused"),
    (b"x: !!set {a, b}", "descriptor_explicit_tag_refused"),
    (b"x: !!omap [a: 1]", "descriptor_explicit_tag_refused"),
    (b"x: !!float .inf", "descriptor_explicit_tag_refused"),
    (b"x: ! 5", "descriptor_explicit_tag_refused"),
    (b"x: !<tag:yaml.org,2002:seq> [a]", "descriptor_explicit_tag_refused"),
    (b"x: 1:30", "descriptor_sexagesimal_refused"),
    (b"1:30: value", "descriptor_sexagesimal_refused"),
    (b'"\\ud800": x', "descriptor_invalid_unicode"),
    (b"x: +.INF", "descriptor_nonfinite"),
    (b"x: .nan", "descriptor_nonfinite"),
    (b"x: 2026-13-45", "descriptor_yaml_invalid"),
    (b"x: " + b"1" * 5000, "descriptor_yaml_invalid"),
    (b"x: 1\n---\nx: 2", "descriptor_yaml_invalid"),
    (b"x: {1: a, 0x1: b}", "descriptor_duplicate_key"),
    (b'x: {id: a, "i\\x64": b}', "descriptor_duplicate_key"),
    ("x: 5".encode("utf-16"), "descriptor_not_utf8"),
])
def test_guard_counterexamples(raw, code):
    with pytest.raises(DescriptorSyntaxError, match="^" + code + "$"):
        parse_descriptor_bytes(raw)


def test_26_descriptor_compatibility_and_byte_identical_rebuild(repo_root, tmp_path, monkeypatch):
    # Exercise Windows text-write translation on every test host.
    write_text = Path.write_text

    def windows_write_text(path, data, **kwargs):
        if kwargs.get("newline") is None:
            kwargs["newline"] = "\r\n"
        return write_text(path, data, **kwargs)

    monkeypatch.setattr(Path, "write_text", windows_write_text)
    paths = sorted((repo_root / "pipelines").glob("*/descriptor.yaml"))
    assert len(paths) == 26
    for path in paths:
        raw = path.read_bytes()
        previous = yaml.safe_load(raw.decode("utf-8"))
        assert parse_descriptor_bytes(raw) == previous
        assert load_descriptor_bytes(raw) == PipelineDescriptor.model_validate(previous)
        assert load_descriptor_bytes(b"\xef\xbb\xbf" + raw) == load_descriptor_file(path)
    for child in ("pipelines", "catalog"):
        shutil.copytree(repo_root / child, tmp_path / child)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert all(r.ok for r in validate_all(tmp_path))
    build_catalog(tmp_path)
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_quoted_descriptive_strings_and_remaining_coercion():
    raw = b'x: "!!binary &anchor *alias << 1:30 .nan \\u2603"\ny: 1_000\n'
    assert parse_descriptor_bytes(raw) == {"x": "!!binary &anchor *alias << 1:30 .nan \u2603", "y": 1000}


def test_scaffold_writer_passes_guard(tmp_path):
    from nirs4all_repository.scaffold import scaffold_pipeline

    recipe = tmp_path / "recipe.json"
    recipe.write_text('[{"class":"sklearn.preprocessing.StandardScaler"}]')
    path = scaffold_pipeline(tmp_path / "output", "example", recipe)
    assert load_descriptor_file(path / "descriptor.yaml").id == "example"


@pytest.mark.parametrize("field,value", [("id", "nl\n"), ("tags", ["x\n"])])
def test_owner_rejects_newline_slug_before_service(make_catalog, field, value):
    from pydantic import ValidationError

    root = make_catalog()
    path = root / "pipelines/demo_pipe/descriptor.yaml"
    data = yaml.safe_load(path.read_bytes())
    data[field] = value
    raw = yaml.safe_dump(data).encode()
    path.write_bytes(raw)
    for call in (lambda: PipelineDescriptor.model_validate(data), lambda: load_descriptor_bytes(raw), lambda: load_descriptor_file(path)):
        with pytest.raises(ValidationError):
            call()
    report = validate_pipeline(root, "demo_pipe")
    assert not report.ok
    assert len(report.errors) == 1 and report.errors[0].startswith("descriptor invalid:")


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
@pytest.mark.parametrize("value", ["2026-11-04\n", "2026-11-04", "2026-11-04T12:34:56Z"])
def test_descriptor_date_fullmatch_preserves_valid_values(make_catalog, field, value):
    from pydantic import ValidationError

    root = make_catalog()
    path = root / "pipelines/demo_pipe/descriptor.yaml"
    data = yaml.safe_load(path.read_bytes())
    data[field] = value
    raw = yaml.safe_dump(data).encode()
    path.write_bytes(raw)
    for call in (lambda: PipelineDescriptor.model_validate(data), lambda: load_descriptor_bytes(raw), lambda: load_descriptor_file(path)):
        if value.endswith("\n"):
            with pytest.raises(ValidationError):
                call()
        else:
            assert getattr(call(), field) == value
    report = validate_pipeline(root, "demo_pipe")
    if value.endswith("\n"):
        assert not report.ok
        assert len(report.errors) == 1 and report.errors[0].startswith("descriptor invalid:")
    else:
        assert report.ok
