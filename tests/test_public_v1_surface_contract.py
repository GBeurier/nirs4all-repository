# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Executable contract for the Repository surface required by the V1 train."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "public-v1-surface.n4a.json"


def _load_checker() -> ModuleType:
    path = ROOT / "scripts" / "check_public_v1_surface.py"
    spec = importlib.util.spec_from_file_location("check_public_v1_surface", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_v1_surface_contract_matches_repository() -> None:
    checker = _load_checker()
    contract = checker._load_contract()

    report = checker.validate_repository_surface(contract)

    assert report["distribution"] == {
        "name": "nirs4all-repository",
        "version": "0.1.12",
        "namespace": "nirs4all_repository",
    }
    assert report["provider_entry_points"] == [
        "get_pipeline_list",
        "get_pipeline",
        "get_bundle",
    ]
    assert len(report["recipe_ids"]) == 5


def test_public_v1_surface_contract_pins_exact_python_train() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    milestones = contract["nirs4all_integration"]["milestones"]

    assert {key: value["version"] for key, value in milestones.items()} == {
        "r1": "0.13.0",
        "r2": "1.0.0rc1",
        "r3": "1.0.0rc2",
    }
    assert all(len(value["head"]) == 40 for value in milestones.values())
    assert all(len(value["tree"]) == 40 for value in milestones.values())
