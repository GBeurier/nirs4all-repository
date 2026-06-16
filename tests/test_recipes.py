# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Tests for recipe parsing, structural validation, and normalisation."""

from __future__ import annotations

import pytest

from nirs4all_repository.recipes import (
    RecipeError,
    normalize_nirs4all_steps,
    recipe_fingerprints,
    to_canonical_json_recipe,
    validate_recipe_structure,
)
from nirs4all_repository.schema import RecipeFormat


def test_normalize_bare_list():
    steps = normalize_nirs4all_steps([{"class": "sklearn.preprocessing.MinMaxScaler"}])
    assert len(steps) == 1


def test_normalize_pipeline_key():
    steps = normalize_nirs4all_steps({"name": "x", "pipeline": [{"class": "A.B"}]})
    assert steps == [{"class": "A.B"}]


def test_normalize_steps_alias():
    steps = normalize_nirs4all_steps({"steps": [{"class": "A.B"}]})
    assert steps == [{"class": "A.B"}]


def test_normalize_rejects_missing_keys():
    with pytest.raises(RecipeError):
        normalize_nirs4all_steps({"foo": 1})


def test_normalize_rejects_empty():
    with pytest.raises(RecipeError):
        normalize_nirs4all_steps([])


def test_validate_nirs4all_structure_ok():
    validate_recipe_structure(
        {"pipeline": [{"class": "sklearn.preprocessing.MinMaxScaler"}, {"model": {"class": "sklearn.linear_model.Ridge"}}]},
        RecipeFormat.nirs4all_pipeline_config,
    )


def test_validate_dagml_dsl_ok():
    validate_recipe_structure([{"class": "A.B"}], RecipeFormat.dagml_pipeline_dsl)


def test_validate_dagml_compiled_requires_keys():
    with pytest.raises(RecipeError):
        validate_recipe_structure({"graph": {}}, RecipeFormat.dagml_compiled_artifact)
    validate_recipe_structure({"graph": {}, "campaign_template": {}}, RecipeFormat.dagml_compiled_artifact)


def test_canonical_json_recipe_wraps_bare_list():
    out = to_canonical_json_recipe([{"class": "A.B"}], RecipeFormat.nirs4all_pipeline_config)
    assert out == {"pipeline": [{"class": "A.B"}]}


def test_canonical_json_recipe_drops_steps_alias():
    out = to_canonical_json_recipe({"name": "x", "steps": [{"class": "A.B"}]}, RecipeFormat.nirs4all_pipeline_config)
    assert "steps" not in out
    assert out["pipeline"] == [{"class": "A.B"}]


def test_fingerprints_nirs4all():
    fp = recipe_fingerprints({"pipeline": [{"class": "A.B"}]}, RecipeFormat.nirs4all_pipeline_config)
    assert "config_sha256" in fp
    assert len(fp["config_sha256"]) == 16


def test_fingerprints_dagml_empty():
    assert recipe_fingerprints([{"class": "A.B"}], RecipeFormat.dagml_pipeline_dsl) == {}
