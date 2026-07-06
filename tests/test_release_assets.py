# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Tests for the GitHub Release asset hygiene check."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_release_assets.py"
SPEC = importlib.util.spec_from_file_location("check_release_assets", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
check_release_assets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_release_assets)


def test_asset_errors_accepts_wheel_and_sdist():
    errors = check_release_assets.asset_errors(
        ["nirs4all_repository-0.1.6-py3-none-any.whl", "nirs4all_repository-0.1.6.tar.gz"],
        min_assets=1,
        require_python_dist=True,
    )
    assert errors == []


def test_asset_errors_rejects_release_without_assets():
    errors = check_release_assets.asset_errors([], min_assets=1, require_python_dist=True)
    assert "expected at least 1 release asset(s), found 0" in errors
    assert "missing wheel asset (*.whl)" in errors
    assert "missing sdist asset (*.tar.gz)" in errors


def test_asset_names_ignores_malformed_asset_entries():
    names = check_release_assets.asset_names({"assets": [{"name": "package.whl"}, {"name": 42}, "bad"]})
    assert names == ["package.whl"]


def test_main_fails_when_release_has_no_assets(monkeypatch, capsys):
    def fake_fetch(repo: str, tag: str | None, token: str | None):
        assert repo == "GBeurier/nirs4all-repository"
        assert tag == "v0.1.5"
        assert token is None
        return {"tag_name": "v0.1.5", "assets": []}

    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(check_release_assets, "github_token", lambda: None)
    monkeypatch.setattr(check_release_assets, "fetch_release", fake_fetch)

    exit_code = check_release_assets.main(["--repo", "GBeurier/nirs4all-repository", "--tag", "v0.1.5"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "release has 0 asset(s): none" in captured.err


def test_main_passes_with_wheel_and_sdist(monkeypatch, capsys):
    def fake_fetch(repo: str, tag: str | None, token: str | None):
        return {
            "tag_name": "v0.1.6",
            "assets": [
                {"name": "nirs4all_repository-0.1.6-py3-none-any.whl"},
                {"name": "nirs4all_repository-0.1.6.tar.gz"},
            ],
        }

    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(check_release_assets, "github_token", lambda: None)
    monkeypatch.setattr(check_release_assets, "fetch_release", fake_fetch)

    exit_code = check_release_assets.main(["--repo", "GBeurier/nirs4all-repository", "--tag", "v0.1.6"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "release assets OK" in captured.out
