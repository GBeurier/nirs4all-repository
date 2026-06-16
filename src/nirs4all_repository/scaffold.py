# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Scaffold a new pipeline bundle from a recipe file (``n4a-repository add``)."""

from __future__ import annotations

from pathlib import Path

import yaml

from .canonical import is_slug
from .recipes import RecipeFormat, load_recipe_file, to_canonical_json_recipe, validate_recipe_structure
from .schema import SCHEMA_VERSION, Framework, utc_date
from .store import CARD_FILENAME, DESCRIPTOR_FILENAME, pipeline_dir

_FRAMEWORK_DEFAULT_FORMAT = {
    Framework.nirs4all: RecipeFormat.nirs4all_pipeline_config,
    Framework.dag_ml: RecipeFormat.dagml_pipeline_dsl,
}


def scaffold_pipeline(
    root: Path,
    pipeline_id: str,
    recipe_path: Path,
    *,
    framework: str = "nirs4all",
    summary: str = "",
) -> Path:
    """Create ``pipelines/<id>/`` from a recipe file and return the bundle directory."""
    if not is_slug(pipeline_id):
        raise ValueError(f"pipeline id must be a slug, got {pipeline_id!r}")
    fw = Framework(framework)
    fmt = _FRAMEWORK_DEFAULT_FORMAT[fw]

    target = pipeline_dir(root, pipeline_id)
    if target.exists():
        raise FileExistsError(f"pipeline directory already exists: {target}")

    recipe = load_recipe_file(recipe_path)
    validate_recipe_structure(recipe, fmt)
    canonical = to_canonical_json_recipe(recipe, fmt)

    target.mkdir(parents=True)
    import json

    (target / "pipeline.json").write_text(json.dumps(canonical, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    descriptor = {
        "schema_version": SCHEMA_VERSION,
        "id": pipeline_id,
        "name": pipeline_id.replace("_", " ").title(),
        "summary": summary or f"{pipeline_id} pipeline.",
        "framework": fw.value,
        "kind": "recipe",
        "task": "regression",
        "tags": [],
        "version": "0.1.0",
        "license": "CeCILL-2.1 OR AGPL-3.0-or-later",
        "created_at": utc_date(),
        "authors": [{"name": "Gregory Beurier", "email": "gregory.beurier@cirad.fr"}],
        "recipe": {"format": fmt.value, "path": "pipeline.json"},
        "provenance": {"generated_by": f"{fw.value} (hand-authored)"},
        "governance": {"status": "draft", "visibility": "public", "trust": "experimental"},
    }
    (target / DESCRIPTOR_FILENAME).write_text(yaml.safe_dump(descriptor, sort_keys=False, allow_unicode=True), encoding="utf-8")
    (target / CARD_FILENAME).write_text(f"# {descriptor['name']}\n\n{descriptor['summary']}\n", encoding="utf-8")
    return target
