#!/usr/bin/env python3
"""Import Studio's authored presets without changing their canonical recipes."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

import yaml

from nirs4all_repository.builder import build_catalog
from nirs4all_repository.canonical import validate_json_value, write_ordered_json
from nirs4all_repository.recipes import RecipeError, normalize_nirs4all_steps, validate_recipe_structure
from nirs4all_repository.schema import RecipeFormat
from nirs4all_repository.security import scan_config


class _UniqueKeyLoader(yaml.SafeLoader):
    """Refuse duplicate source keys before YAML can silently overwrite values."""


def _unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise RecipeError(f"duplicate YAML object key: {key!r}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def sync(studio: Path, root: Path) -> None:
    """Write a provenance snapshot and one repository bundle per task variant."""
    presets = []
    source_files = {}
    sources = []
    for source in sorted((studio / "api" / "presets").glob("*.yaml")):
        data = yaml.load(source.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
        # YAML is source transport only. Refuse values JSON would coerce, and check
        # every variant before writing any bundle or changing the snapshot.
        validate_json_value(data)
        for variant in data["variants"].values():
            recipe = {key: value for key, value in variant.items() if key != "format"}
            validate_recipe_structure(recipe, RecipeFormat.nirs4all_pipeline_config)
            scan_config(recipe, RecipeFormat.nirs4all_pipeline_config).raise_for_findings()
        sources.append((source, data))
    if not sources:
        raise ValueError(f"No Studio presets found in {studio}")
    commit = subprocess.check_output(["git", "-C", str(studio), "rev-parse", "HEAD"], text=True).strip()
    for source, data in sources:
        source_files[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
        default = data["default_variant"]
        default_recipe = {key: value for key, value in data["variants"][default].items() if key != "format"}
        data.update(available_variants=list(data["variants"]), steps_count=len(normalize_nirs4all_steps(default_recipe)))
        data["repository_variants"] = {}
        for task, variant in data["variants"].items():
            pid = f"studio_{data['id']}_{task}"
            data["repository_variants"][task] = pid
            target = root / "pipelines" / pid
            target.mkdir(parents=True, exist_ok=True)
            recipe = {key: value for key, value in variant.items() if key != "format"}
            write_ordered_json(target / "pipeline.json", recipe)
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
            (target / "descriptor.yaml").write_text(yaml.safe_dump(descriptor, sort_keys=False, allow_unicode=True), encoding="utf-8", newline="\n")
            (target / "card.md").write_text(
                f"# {data['name']}\n\n{data['description']}\n\n"
                f"Imported unchanged from the Studio **{task}** preset. Complexity: {data['complexity']}/10.\n\n"
                "This recipe has not been evaluated by the repository.\n", encoding="utf-8", newline="\n",
            )
        presets.append(data)
    snapshot = {
        "source": "nirs4all-studio/api/presets",
        "commit": commit,
        "files_sha256": source_files,
        "presets": sorted(presets, key=lambda preset: preset["complexity"]),
    }
    write_ordered_json(root / "catalog" / "studio-presets.json", snapshot)
    build_catalog(root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studio", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    sync(args.studio.resolve(), args.root.resolve())
