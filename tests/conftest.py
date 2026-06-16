# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Shared pytest fixtures: the repo root and a synthetic catalogue factory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def repo_root() -> Path:
    """The actual repository checkout root (carries the seed catalogue)."""
    return REPO_ROOT


@pytest.fixture
def make_catalog(tmp_path: Path):
    """Return a factory that builds a synthetic catalogue root with one pipeline.

    The factory writes ``pipelines/<id>/{descriptor.yaml, pipeline.json, card.md}`` and
    a ``catalog/`` directory, then returns the catalogue root path.
    """

    def factory(
        pipeline_id: str = "demo_pipe",
        *,
        framework: str = "nirs4all",
        recipe: dict | list | None = None,
        descriptor_overrides: dict | None = None,
    ) -> Path:
        root = tmp_path / "catalog_root"
        bundle = root / "pipelines" / pipeline_id
        bundle.mkdir(parents=True)
        (root / "catalog").mkdir(exist_ok=True)

        if recipe is None:
            recipe = {
                "name": "Demo",
                "pipeline": [
                    {"class": "sklearn.preprocessing.MinMaxScaler"},
                    {"model": {"class": "sklearn.cross_decomposition.PLSRegression", "params": {"n_components": 5}}},
                ],
            }
        fmt = "nirs4all/pipeline-config" if framework == "nirs4all" else "dag-ml/pipeline-dsl"
        (bundle / "pipeline.json").write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8")
        (bundle / "card.md").write_text("# Demo\n\nA demo pipeline.\n", encoding="utf-8")

        descriptor = {
            "schema_version": 1,
            "id": pipeline_id,
            "name": "Demo Pipeline",
            "summary": "A synthetic demo pipeline for tests.",
            "framework": framework,
            "kind": "recipe",
            "task": "regression",
            "tags": ["demo", "pls"],
            "version": "1.0.0",
            "license": "CeCILL-2.1 OR AGPL-3.0-or-later",
            "created_at": "2026-06-17",
            "authors": [{"name": "Test Author"}],
            "recipe": {"format": fmt, "path": "pipeline.json"},
            "provenance": {"generated_by": "test"},
            "governance": {"status": "draft", "visibility": "public", "trust": "community"},
        }
        if descriptor_overrides:
            descriptor.update(descriptor_overrides)
        (bundle / "descriptor.yaml").write_text(yaml.safe_dump(descriptor, sort_keys=False), encoding="utf-8")
        return root

    return factory
