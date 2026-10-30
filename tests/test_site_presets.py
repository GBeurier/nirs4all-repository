"""Parity and static rendering checks for the imported Studio preset gallery."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from nirs4all_repository.site.build import build_site
from nirs4all_repository.site.presets import load_studio_presets
from nirs4all_repository.store import load_index
from nirs4all_repository.validate import validate_pipeline

ROOT = Path(__file__).resolve().parents[1]


def test_every_studio_variant_matches_the_source_snapshot():
    index = load_index(ROOT)
    studio = load_studio_presets(ROOT, index)
    assert studio is not None
    assert len(studio["presets"]) == 10
    assert [p["complexity"] for p in studio["presets"]] == sorted(p["complexity"] for p in studio["presets"])
    for preset in studio["presets"]:
        assert preset["available_variants"] == ["regression", "classification"]
        for pid in preset["repository_variants"].values():
            report = validate_pipeline(ROOT, pid)
            assert report.ok, report


def test_static_gallery_uses_shared_cards_and_keeps_variant_links(tmp_path):
    output = build_site(ROOT, tmp_path / "site")
    page = (output / "index.html").read_text(encoding="utf-8")
    assert page.count('class="n4-preset-card"') == 10
    assert "Additional repository recipes (6)" in page
    studio = json.loads((ROOT / "catalog" / "studio-presets.json").read_text(encoding="utf-8"))
    for preset in studio["presets"]:
        assert preset["name"] in page
        for task, pid in preset["repository_variants"].items():
            assert f'href="pipeline/{pid}.html"' in page
            assert (output / "pipeline" / f"{pid}.html").is_file()
            recipe = output / "data" / "pipelines" / pid / "pipeline.json"
            assert json.loads(recipe.read_text())["pipeline"] == preset["variants"][task]["pipeline"]


def test_stale_card_snapshot_is_refused(tmp_path):
    shutil.copytree(ROOT / "catalog", tmp_path / "catalog")
    source = tmp_path / "catalog" / "studio-presets.json"
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="cards are stale"):
        load_studio_presets(tmp_path, load_index(ROOT))


def test_custom_catalogue_does_not_require_studio_artifacts(tmp_path):
    assert load_studio_presets(tmp_path, {"pipelines": {}}) is None
