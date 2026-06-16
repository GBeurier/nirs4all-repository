# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Tests for the n4a-repository CLI via Typer's CliRunner."""

from __future__ import annotations

from typer.testing import CliRunner

from nirs4all_repository.builder import build_catalog
from nirs4all_repository.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_validate_all(make_catalog):
    root = make_catalog("demo_pipe")
    build_catalog(root)
    result = runner.invoke(app, ["validate", "--all", "--root", str(root)])
    assert result.exit_code == 0, result.stdout
    assert "valid" in result.stdout


def test_scan(make_catalog):
    root = make_catalog("demo_pipe")
    build_catalog(root)
    result = runner.invoke(app, ["scan", "demo_pipe", "--root", str(root)])
    assert result.exit_code == 0


def test_scan_blocks_injection(make_catalog):
    root = make_catalog("evil", recipe={"pipeline": [{"class": "os.system"}]})
    build_catalog(root)
    result = runner.invoke(app, ["scan", "evil", "--root", str(root)])
    assert result.exit_code == 1


def test_build_command(make_catalog):
    root = make_catalog("demo_pipe")
    result = runner.invoke(app, ["build", "--root", str(root)])
    assert result.exit_code == 0
    assert (root / "catalog" / "index.json").is_file()


def test_publish_reports_blockers(make_catalog):
    root = make_catalog(
        "demo_pipe",
        descriptor_overrides={"governance": {"status": "draft", "visibility": "public", "trust": "official"},
                              "reference": {"source": "nirs4all-datasets", "name": "demo"},
                              "evaluation": {"metric": "rmse", "status": "unvalidated"}},
    )
    build_catalog(root)
    result = runner.invoke(app, ["publish", "demo_pipe", "--root", str(root)])
    assert result.exit_code == 1  # not yet validated
