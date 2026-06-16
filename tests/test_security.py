# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Tests for the recipe class allow-list and the pickle-opcode scan."""

from __future__ import annotations

import pickle

from nirs4all_repository.schema import RecipeFormat
from nirs4all_repository.security import scan_config, scan_pickle_bytes


def test_scan_config_clean():
    recipe = {"pipeline": [{"class": "sklearn.preprocessing.MinMaxScaler"}, {"class": "nirs4all.operators.transforms.StandardNormalVariate"}]}
    result = scan_config(recipe, RecipeFormat.nirs4all_pipeline_config)
    assert result.ok, result.findings


def test_scan_config_blocks_injection():
    recipe = {"pipeline": [{"class": "os.system"}]}
    result = scan_config(recipe, RecipeFormat.nirs4all_pipeline_config)
    assert not result.ok
    assert any("os" in f for f in result.findings)


def test_scan_config_blocks_builtins_eval():
    recipe = {"pipeline": [{"class": "builtins.eval"}]}
    result = scan_config(recipe, RecipeFormat.nirs4all_pipeline_config)
    assert not result.ok


def test_scan_config_extra_allowlist_local_only():
    recipe = {"pipeline": [{"class": "mypackage.MyModel"}]}
    blocked = scan_config(recipe, RecipeFormat.nirs4all_pipeline_config)
    assert not blocked.ok
    allowed = scan_config(recipe, RecipeFormat.nirs4all_pipeline_config, extra_allowlist=("mypackage",))
    assert allowed.ok


def test_pickle_scan_safe_payload():
    # A plain list of floats pickles to safe opcodes (no GLOBAL imports).
    result = scan_pickle_bytes(pickle.dumps([1.0, 2.0, 3.0]))
    assert result.ok, result.findings


def test_pickle_scan_flags_dangerous_global():
    payload = b"c__builtin__\neval\n(S'1+1'\ntR."
    result = scan_pickle_bytes(payload)
    assert not result.ok


def test_pickle_scan_flags_os_system():
    payload = b"cos\nsystem\n(S'echo hi'\ntR."
    result = scan_pickle_bytes(payload)
    assert not result.ok
    assert any("os" in f for f in result.findings)
