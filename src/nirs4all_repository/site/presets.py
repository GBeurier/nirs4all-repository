"""Read the catalogue's build-time nirs4all-ui rendering, with recipe parity checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def load_studio_presets(root: Path, index: dict[str, Any]) -> dict[str, Any] | None:
    """Return verified static cards; ordinary third-party catalogues need no Node setup."""
    source = root / "catalog" / "studio-presets.json"
    if not source.is_file():
        return None
    snapshot = json.loads(source.read_text(encoding="utf-8"))
    rendered = json.loads((source.parent / "studio-presets.cards.json").read_text(encoding="utf-8"))
    if rendered["source_sha256"] != hashlib.sha256(source.read_bytes()).hexdigest():
        raise ValueError("Studio preset cards are stale; run npm run build:cards")
    for preset in snapshot["presets"]:
        if preset["id"] not in rendered["cards"]:
            raise ValueError(f"Missing Studio preset card: {preset['id']}")
        for task, pid in preset["repository_variants"].items():
            entry = index["pipelines"][pid]
            recipe = json.loads((root / "pipelines" / pid / entry["recipe"]["relpath"]).read_text(encoding="utf-8"))
            if recipe["pipeline"] != preset["variants"][task]["pipeline"]:
                raise ValueError(f"Studio preset recipe differs from snapshot: {pid}")
    return {**snapshot, **rendered}
