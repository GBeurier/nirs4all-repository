"""Read the catalogue's build-time nirs4all-ui rendering, with recipe parity checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..canonical import ordered_json
from ..recipes import load_recipe_file, validate_recipe_structure
from ..schema import RecipeFormat


def load_studio_presets(root: Path, index: dict[str, Any]) -> dict[str, Any] | None:
    """Return verified static cards; ordinary third-party catalogues need no Node setup."""
    source = root / "catalog" / "studio-presets.json"
    if not source.is_file():
        return None
    snapshot = load_recipe_file(source)
    rendered = json.loads((source.parent / "studio-presets.cards.json").read_text(encoding="utf-8"))
    if rendered["source_sha256"] != hashlib.sha256(source.read_bytes()).hexdigest():
        raise ValueError("Studio preset cards are stale; run npm run build:cards")
    for preset in snapshot["presets"]:
        if preset["id"] not in rendered["cards"]:
            raise ValueError(f"Missing Studio preset card: {preset['id']}")
        variants = preset["variants"]
        mapping = preset.get("repository_variants")
        if not isinstance(mapping, dict) or not variants or set(mapping) != set(variants):
            raise ValueError(f"Studio preset variant mapping is incomplete: {preset['id']}")
        for task, pid in mapping.items():
            entry = index["pipelines"][pid]
            recipe = load_recipe_file(root / "pipelines" / pid / entry["recipe"]["relpath"])
            validate_recipe_structure(recipe, RecipeFormat(entry["recipe"]["format"]))
            expected = {key: value for key, value in preset["variants"][task].items() if key != "format"}
            if ordered_json(recipe) != ordered_json(expected):
                raise ValueError(f"Studio preset recipe differs from snapshot: {pid}")
    return {**snapshot, **rendered}
