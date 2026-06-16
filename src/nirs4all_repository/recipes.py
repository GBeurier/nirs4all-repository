# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Recipe parsing, structural validation, and normalisation.

The repository validates recipes *structurally* without importing the heavy
frameworks, so the hermetic CI gate stays dependency-light. Strict, framework-level
validation (``nirs4all.PipelineConfigs`` / dag-ml compile) is opt-in and lives in
:mod:`nirs4all_repository.evaluate` and the validators that request it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .canonical import nirs4all_config_hash
from .schema import RecipeFormat

#: Step keywords recognised by a nirs4all pipeline config (mirrors nirs4all ALL_KEYWORDS).
NIRS4ALL_STEP_KEYWORDS = frozenset(
    {
        "class",
        "params",
        "model",
        "meta_model",
        "y_processing",
        "feature_augmentation",
        "branch",
        "merge",
        "name",
        "finetune_params",
        "action",
        "_or_",
        "_range_",
        "pick",
        "count",
    }
)


class RecipeError(ValueError):
    """Raised when a recipe is structurally invalid for its declared format."""


def load_recipe_text(text: str, *, filename: str = "") -> Any:
    """Parse recipe *text* as JSON or YAML (YAML is a superset of JSON)."""
    name = filename.lower()
    if name.endswith(".json"):
        return json.loads(text)
    # YAML safely loads JSON too; use it as the general parser.
    return yaml.safe_load(text)


def load_recipe_file(path: Path) -> Any:
    """Parse the recipe file at *path*."""
    return load_recipe_text(path.read_text(encoding="utf-8"), filename=path.name)


def normalize_nirs4all_steps(recipe: Any) -> list[Any]:
    """Return the canonical step list from a nirs4all recipe.

    Accepts a bare step list, ``{"pipeline": [...]}``, or ``{"steps": [...]}`` (the
    ``steps`` alias is normalised to the step list). Raises :class:`RecipeError` on any
    other shape.
    """
    if isinstance(recipe, list):
        steps = recipe
    elif isinstance(recipe, dict):
        if "pipeline" in recipe:
            steps = recipe["pipeline"]
        elif "steps" in recipe:
            steps = recipe["steps"]
        else:
            raise RecipeError("nirs4all recipe object must contain a 'pipeline' or 'steps' list")
    else:
        raise RecipeError(f"nirs4all recipe must be a list or object, got {type(recipe).__name__}")
    if not isinstance(steps, list) or not steps:
        raise RecipeError("nirs4all recipe steps must be a non-empty list")
    return steps


def _check_nirs4all_step(step: Any, index: int) -> None:
    if isinstance(step, str):
        return  # a bare dotted class path is allowed
    if not isinstance(step, dict):
        raise RecipeError(f"step {index} must be a string or mapping, got {type(step).__name__}")
    if not step:
        raise RecipeError(f"step {index} is an empty mapping")
    # Stay forward-compatible with nirs4all (don't reject unknown keys), but a step must
    # carry at least one recognised keyword.
    if not (set(step) & NIRS4ALL_STEP_KEYWORDS):
        raise RecipeError(f"step {index} has no recognised nirs4all keyword: {sorted(step)}")


def validate_nirs4all_structure(recipe: Any) -> list[Any]:
    """Structurally validate a nirs4all recipe; return the normalised step list."""
    steps = normalize_nirs4all_steps(recipe)
    for index, step in enumerate(steps):
        _check_nirs4all_step(step, index)
    return steps


def validate_dagml_dsl_structure(recipe: Any) -> None:
    """Structurally validate a dag-ml pipeline DSL recipe."""
    if isinstance(recipe, list):
        if not recipe:
            raise RecipeError("dag-ml DSL step list must be non-empty")
        return
    if isinstance(recipe, dict):
        if not recipe:
            raise RecipeError("dag-ml DSL object must be non-empty")
        return
    raise RecipeError(f"dag-ml DSL must be a list or object, got {type(recipe).__name__}")


def validate_dagml_compiled_structure(recipe: Any) -> None:
    """Structurally validate a dag-ml CompiledPipelineArtifact recipe."""
    if not isinstance(recipe, dict):
        raise RecipeError("dag-ml compiled artifact must be an object")
    missing = {"graph", "campaign_template"} - set(recipe)
    if missing:
        raise RecipeError(f"dag-ml compiled artifact missing required keys: {sorted(missing)}")


def validate_recipe_structure(recipe: Any, fmt: RecipeFormat) -> None:
    """Structurally validate *recipe* against its declared *fmt*."""
    if fmt is RecipeFormat.nirs4all_pipeline_config:
        validate_nirs4all_structure(recipe)
    elif fmt is RecipeFormat.dagml_pipeline_dsl:
        validate_dagml_dsl_structure(recipe)
    elif fmt is RecipeFormat.dagml_compiled_artifact:
        validate_dagml_compiled_structure(recipe)
    else:  # pragma: no cover - exhaustive over the enum
        raise RecipeError(f"unknown recipe format {fmt!r}")


def to_canonical_json_recipe(recipe: Any, fmt: RecipeFormat) -> Any:
    """Return the canonical-JSON-serialisable form of *recipe*.

    For nirs4all configs, objects are preserved but the step list is normalised to a
    ``pipeline`` key so served recipes are uniform; bare lists are wrapped. For dag-ml
    formats the recipe is returned unchanged (already a JSON object/list).
    """
    if fmt is RecipeFormat.nirs4all_pipeline_config:
        steps = normalize_nirs4all_steps(recipe)
        if isinstance(recipe, dict):
            out = {key: value for key, value in recipe.items() if key != "steps"}
            out["pipeline"] = steps
            return out
        return {"pipeline": steps}
    return recipe


def recipe_fingerprints(recipe: Any, fmt: RecipeFormat) -> dict[str, str]:
    """Compute the framework-native identity fingerprints for *recipe*."""
    if fmt is RecipeFormat.nirs4all_pipeline_config:
        steps = normalize_nirs4all_steps(recipe)
        return {"config_sha256": nirs4all_config_hash(steps)}
    return {}
