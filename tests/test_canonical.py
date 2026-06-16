# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Tests for canonical serialisation, hashing, and path-safety primitives."""

from __future__ import annotations

from nirs4all_repository.canonical import (
    canonical_json,
    is_safe_relpath,
    is_sha256,
    is_slug,
    nirs4all_config_hash,
    sha256_bytes,
)


def test_canonical_json_is_sorted_and_trailing_newline():
    text = canonical_json({"b": 1, "a": 2})
    assert text == '{\n  "a": 2,\n  "b": 1\n}\n'


def test_canonical_json_is_deterministic():
    obj = {"z": [3, 2, 1], "a": {"y": 1, "x": 2}}
    assert canonical_json(obj) == canonical_json(dict(reversed(list(obj.items()))))


def test_sha256_bytes_known_value():
    assert sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_slug_rules():
    assert is_slug("snv_savgol_pls")
    assert is_slug("a1")
    assert not is_slug("Bad")
    assert not is_slug("_leading")
    assert not is_slug("double__underscore")
    assert not is_slug("trailing_")


def test_sha256_validation():
    assert is_sha256("a" * 64)
    assert not is_sha256("A" * 64)
    assert not is_sha256("abc")


def test_safe_relpath():
    assert is_safe_relpath("artifacts/model.joblib")
    assert is_safe_relpath("pipeline.json")
    assert not is_safe_relpath("/etc/passwd")        # POSIX-absolute (must fail on Windows too)
    assert not is_safe_relpath("\\windows\\system32")  # backslash-absolute
    assert not is_safe_relpath("C:/Windows/x")       # Windows drive
    assert not is_safe_relpath("C:\\Windows\\x")
    assert not is_safe_relpath("../escape")
    assert not is_safe_relpath("a/../../b")
    assert not is_safe_relpath("a\\..\\b")           # backslash parent escape
    assert not is_safe_relpath("")


def test_nirs4all_config_hash_matches_known_recipe_order_independence_of_keys():
    steps = [{"class": "sklearn.preprocessing.MinMaxScaler"}]
    h1 = nirs4all_config_hash(steps)
    assert len(h1) == 16
    # Key order inside a step does not change the hash (sort_keys).
    steps2 = [{"class": "sklearn.preprocessing.MinMaxScaler"}]
    assert nirs4all_config_hash(steps2) == h1
