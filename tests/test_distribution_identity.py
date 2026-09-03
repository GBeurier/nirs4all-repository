# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Tests for exact release distribution and tag identity."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_distribution_identity.py"
SPEC = importlib.util.spec_from_file_location("check_distribution_identity", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
check_distribution_identity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_distribution_identity)


def test_identity_accepts_exact_release_pair() -> None:
    names = ["nirs4all_repository-0.1.11-py3-none-any.whl", "nirs4all_repository-0.1.11.tar.gz"]
    assert check_distribution_identity.identity_errors(names, version="0.1.11", release_tag="v0.1.11") == []


def test_identity_rejects_tag_version_drift() -> None:
    names = ["nirs4all_repository-0.1.11-py3-none-any.whl", "nirs4all_repository-0.1.11.tar.gz"]
    errors = check_distribution_identity.identity_errors(names, version="0.1.11", release_tag="v0.1.12")
    assert errors == ["release tag 'v0.1.12' does not match VERSION '0.1.11'"]


def test_identity_rejects_missing_or_wrong_distribution() -> None:
    names = ["nirs4all_repository-0.1.10-py3-none-any.whl"]
    errors = check_distribution_identity.identity_errors(names, version="0.1.11")
    assert len(errors) == 1
    assert "distribution identity mismatch" in errors[0]
