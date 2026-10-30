#!/usr/bin/env python3
"""Import Studio's authored presets without changing their canonical recipes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import yaml

from nirs4all_repository.builder import build_catalog


def sync(studio: Path, root: Path) -> None:
    """Write a provenance snapshot and one repository bundle per task variant."""
    presets = []
    source_files = {}
    for source in sorted((studio / "api" / "presets").glob("*.yaml")):
        data = yaml.safe_load(source.read_text(encoding="utf-8"))
        source_files[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
        default = data["default_variant"]
        data.update(available_variants=list(data["variants"]), steps_count=len(data["variants"][default]["pipeline"]))
        data["repository_variants"] = {}
        for task, variant in data["variants"].items():
            pid = f"studio_{data['id']}_{task}"
            data["repository_variants"][task] = pid
            target = root / "pipelines" / pid
            target.mkdir(parents=True, exist_ok=True)
            recipe = {"pipeline": variant["pipeline"]}
            (target / "pipeline.json").write_text(json.dumps(recipe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            descriptor = {
                "schema_version": 1, "id": pid,
                "name": f"{data['name']} ({task.title()})", "summary": data["description"],
                "framework": "nirs4all", "kind": "recipe", "task": task,
                "tags": ["studio_preset", data["id"], task], "version": "1.0.0",
                "license": "CeCILL-2.1 OR AGPL-3.0-or-later", "created_at": "2026-10-30",
                "authors": [{"name": "Gregory Beurier", "affiliation": "CIRAD"}],
                "recipe": {"format": "nirs4all/pipeline-config", "path": "pipeline.json"},
                "provenance": {"generated_by": "nirs4all-studio preset import", "source": f"nirs4all-studio/api/presets/{source.name}"},
                "governance": {"status": "draft", "visibility": "public", "trust": "community"},
            }
            (target / "descriptor.yaml").write_text(yaml.safe_dump(descriptor, sort_keys=False, allow_unicode=True), encoding="utf-8")
            (target / "card.md").write_text(
                f"# {data['name']}\n\n{data['description']}\n\n"
                f"Imported unchanged from the Studio **{task}** preset. Complexity: {data['complexity']}/10.\n\n"
                "This recipe has not been evaluated by the repository.\n", encoding="utf-8",
            )
        presets.append(data)
    if not presets:
        raise ValueError(f"No Studio presets found in {studio}")
    snapshot = {
        "source": "nirs4all-studio/api/presets",
        "commit": subprocess.check_output(["git", "-C", str(studio), "rev-parse", "HEAD"], text=True).strip(),
        "files_sha256": source_files,
        "presets": sorted(presets, key=lambda preset: preset["complexity"]),
    }
    (root / "catalog" / "studio-presets.json").write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    build_catalog(root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studio", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    sync(args.studio.resolve(), args.root.resolve())
