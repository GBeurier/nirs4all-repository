# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Lossless recipe parsing, structural validation, and requirement observations.

The repository validates recipes *structurally* without importing the heavy
frameworks, so the hermetic CI gate stays dependency-light. Strict, framework-level
validation via ``nirs4all.PipelineConfigs`` is opt-in; DAG-ML compilation remains
an owner responsibility, not a Repository check.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import nirs4all_config_hash, validate_json_value
from .schema import EXECUTION_REQUIREMENTS_UNKNOWN, Framework, RecipeFormat

#: Structural admission vocabulary, not a compiler or an exhaustive owner schema.
NIRS4ALL_STEP_KEYWORDS = frozenset(
    {
        "class",
        "function",
        "instance",
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
        "_cartesian_",
        "_range_",
        "pick",
        "count",
    }
)


class RecipeError(ValueError):
    """Raised when a recipe is structurally invalid for its declared format."""


def load_recipe_text(text: str, *, filename: str = "") -> Any:
    """Parse strict JSON without coercing keys, scalars, or recipe shapes."""
    if filename and Path(filename).suffix.lower() != ".json":
        raise RecipeError("recipe files must be strict JSON (.json); convert explicitly before admission")
    try:
        recipe = json.loads(text, object_pairs_hook=_unique_object)
        validate_json_value(recipe)
    except (ValueError, TypeError) as exc:
        raise RecipeError(f"recipe is not lossless strict JSON: {exc}") from exc
    return recipe


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RecipeError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def load_recipe_file(path: Path) -> Any:
    """Parse the recipe file at *path*."""
    return load_recipe_text(path.read_text(encoding="utf-8"), filename=path.name)


def normalize_nirs4all_steps(recipe: Any) -> list[Any]:
    """Select a nirs4all step list for structural checks and legacy fingerprints.

    Accepts a bare list or an object containing exactly one of ``pipeline`` and
    ``steps``. Returns the list without rewriting the containing recipe.
    """
    if isinstance(recipe, list):
        steps = recipe
    elif isinstance(recipe, dict):
        if "pipeline" in recipe and "steps" in recipe:
            raise RecipeError("nirs4all recipe must contain exactly one of 'pipeline' or 'steps', not both")
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
    """Structurally validate a nirs4all recipe; return its selected step list."""
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
    try:
        validate_json_value(recipe)
    except (ValueError, TypeError) as exc:
        raise RecipeError(f"recipe is not lossless strict JSON: {exc}") from exc
    if fmt is RecipeFormat.nirs4all_pipeline_config:
        validate_nirs4all_structure(recipe)
    elif fmt is RecipeFormat.dagml_pipeline_dsl:
        validate_dagml_dsl_structure(recipe)
    elif fmt is RecipeFormat.dagml_compiled_artifact:
        validate_dagml_compiled_structure(recipe)
    else:  # pragma: no cover - exhaustive over the enum
        raise RecipeError(f"unknown recipe format {fmt!r}")


def recipe_class_refs(recipe: Any, fmt: RecipeFormat) -> list[str]:
    """Observe explicit component references and executable recipe-node strings.

    nirs4all serializes class/function/instance/enum descriptors. DAG-ML additionally
    carries opaque operator descriptors (class/function/ref/type) in DSL steps and
    compiled graph nodes. Explicit callable descriptors inside operators are scanned
    conservatively; this does not assert that an owner can execute them.

    Visit every container so explicit references nested in params or metadata cannot
    hide. Bare strings only count in step/component contexts, never in ordinary
    parameter, provenance, node-id or display fields. No imports or alias resolution.
    """
    found: list[str] = []
    component_keys = {
        "model", "meta_model", "preprocessing", "processing", "transform",
        "y_processing", "y_transform", "split", "tag", "exclude", "filter",
        "sample_filter", "augmentation", "sample_augmentation", "feature_augmentation",
        "data_generation", "generation", "chart", "tuner", "finetune",
    }
    choices = {"_or_", "_cartesian_", "_chain_", "_zip_"}

    def reference(value: Any, *, explicit: bool = False) -> None:
        if not isinstance(value, str):
            walk(value)
        elif explicit or value.startswith(("n4m:", "n4m.")) or python_reference_root(value) is not None:
            found.append(value)

    def walk(node: Any, context: str = "data") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"class", "function", "instance", "enum"}:
                    reference(value, explicit=True)
                elif context == "component" and key in {"ref", "type", "callable"}:
                    reference(value)
                elif context in {"root", "step", "branch", "named_branches"} and key in {"pipeline", "steps"}:
                    walk(value, "named_branches" if isinstance(value, dict) else "step")
                elif context == "root" and key == "graph" and fmt is RecipeFormat.dagml_compiled_artifact:
                    walk(value, "graph")
                elif context == "graph" and key == "nodes":
                    walk(value, "step")
                elif (context == "step" and key == "operator" and fmt is not RecipeFormat.nirs4all_pipeline_config) or (
                    context in {"step", "component"} and key in component_keys | choices
                ):
                    walk(value, "component")
                elif context in {"step", "component"} and key in {"branch", "concat_transform"}:
                    walk(value, "named_branches")
                elif context in {"step", "branch"} and key in {"branches", "stages"}:
                    walk(value, "branch")
                elif (context == "step" and key == "tail") or (context == "named_branches" and isinstance(value, (list, dict))):
                    walk(value, "step")
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item, "step" if context == "named_branches" else context)
        elif isinstance(node, str) and context in {"step", "component"}:
            reference(node)

    walk(recipe, "step" if isinstance(recipe, list) else "root")
    return found


def python_reference_root(reference: str) -> str | None:
    """Return the root of an import-shaped reference, without resolving namespaces."""
    parts = reference.split(".")
    if reference.startswith(("n4m:", "n4m.")) or len(parts) < 2 or not all(part.isidentifier() for part in parts):
        return None
    return parts[0]


def execution_requirements(recipe: Any, framework: Framework, fmt: RecipeFormat) -> dict[str, Any]:
    """Derive observations, never execution qualification, from a validated recipe.

    Versions, execution profiles, operations and artifact versions require evidence
    from their owners; neither class imports nor storage establish runtime support.
    """
    validate_recipe_structure(recipe, fmt)
    return {
        "schema": "nirs4all-repository.execution-requirements.v1",
        "framework": framework.value,
        "recipe_format": fmt.value,
        "python_module_roots": sorted({root for ref in recipe_class_refs(recipe, fmt) if (root := python_reference_root(ref)) is not None}),
        "unknown": list(EXECUTION_REQUIREMENTS_UNKNOWN),
    }


def recipe_fingerprints(recipe: Any, fmt: RecipeFormat) -> dict[str, str]:
    """Compute legacy step-only fingerprints; not full recipe or runtime identity."""
    validate_recipe_structure(recipe, fmt)
    if fmt is RecipeFormat.nirs4all_pipeline_config:
        steps = normalize_nirs4all_steps(recipe)
        return {"config_sha256": nirs4all_config_hash(steps)}
    return {}
