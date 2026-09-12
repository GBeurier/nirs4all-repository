# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Release-train compatibility gates for the optional nirs4all integration."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from types import ModuleType

from packaging.requirements import Requirement

from nirs4all_repository.schema import PipelineDescriptor
from nirs4all_repository.validate import _strict_check


def _nirs4all_requirement() -> Requirement:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    requirements = project["optional-dependencies"]["nirs4all"]
    assert len(requirements) == 1
    return Requirement(requirements[0])


def test_nirs4all_extra_covers_legacy_r1_r2_and_r3() -> None:
    requirement = _nirs4all_requirement()

    # Retain the historical supported line while admitting the exact native train.
    for version in ("0.10.0", "0.12.10", "0.13.0", "1.0.0rc1", "1.0.0rc2"):
        assert requirement.specifier.contains(version), version

    assert not requirement.specifier.contains("2.0.0.dev0")
    assert not requirement.specifier.contains("2.0.0")


def test_strict_validation_uses_public_nirs4all_export(monkeypatch) -> None:
    calls: list[object] = []
    fake_nirs4all = ModuleType("nirs4all")

    class PipelineConfigs:
        def __init__(self, recipe: object) -> None:
            calls.append(recipe)

    fake_nirs4all.PipelineConfigs = PipelineConfigs  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "nirs4all", fake_nirs4all)

    recipe = [{"y_processing": "SNV"}]
    descriptor = PipelineDescriptor.model_validate(
        {
            "schema_version": 1,
            "id": "train_compat",
            "name": "Train compatibility",
            "summary": "Release-train validation fixture.",
            "framework": "nirs4all",
            "kind": "recipe",
            "task": "regression",
            "version": "1.0.0",
            "license": "CeCILL-2.1 OR AGPL-3.0-or-later",
            "created_at": "2026-09-03",
            "authors": [{"name": "Test Author"}],
            "recipe": {"format": "nirs4all/pipeline-config", "path": "pipeline.json"},
        }
    )
    assert _strict_check(recipe, descriptor) == []
    assert calls == [recipe]
