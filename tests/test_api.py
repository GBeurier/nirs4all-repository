# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Tests for the public API: list / card / get / Pipeline / site rendering."""

from __future__ import annotations

import pytest

import nirs4all_repository as n4r
from nirs4all_repository.bridge import BridgeError
from nirs4all_repository.builder import build_catalog
from nirs4all_repository.site import build_site


def test_list_and_filters(make_catalog):
    root = make_catalog("demo_pipe")
    build_catalog(root)
    entries = n4r.list(root=root)
    assert [e["id"] for e in entries] == ["demo_pipe"]
    assert n4r.list(root=root, framework="nirs4all")
    assert n4r.list(root=root, framework="dag-ml") == []
    assert n4r.list(root=root, tag="demo")
    assert n4r.list(root=root, tag="absent") == []


def test_card_returns_descriptor(make_catalog):
    root = make_catalog("demo_pipe")
    build_catalog(root)
    card = n4r.card("demo_pipe", root=root)
    assert card["id"] == "demo_pipe"
    assert card["recipe"]["format"] == "nirs4all/pipeline-config"


def test_get_local_first_and_bridge(make_catalog):
    root = make_catalog("demo_pipe")
    build_catalog(root)
    pipe = n4r.get("demo_pipe", root=root)
    assert pipe.id == "demo_pipe"
    config = pipe.to_nirs4all()
    assert "pipeline" in config
    with pytest.raises(BridgeError):
        pipe.to_dagml()


def test_get_verifies_and_detects_tamper(make_catalog):
    root = make_catalog("demo_pipe")
    build_catalog(root)
    bundle = root / "pipelines" / "demo_pipe"
    (bundle / "pipeline.json").write_text('{"pipeline": [{"class": "sklearn.linear_model.Ridge"}]}\n', encoding="utf-8")
    with pytest.raises(BridgeError):
        n4r.get("demo_pipe", root=root)


def test_get_unknown_pipeline(make_catalog):
    root = make_catalog("demo_pipe")
    build_catalog(root)
    with pytest.raises(Exception):
        n4r.get("nope", root=root)


def test_site_build_and_escaping(make_catalog, tmp_path):
    root = make_catalog("demo_pipe")
    # Inject an XSS attempt into the card.
    (root / "pipelines" / "demo_pipe" / "card.md").write_text("# Demo\n\n<script>alert(1)</script>\n", encoding="utf-8")
    build_catalog(root)
    out = build_site(root, tmp_path / "site")
    assert (out / "index.html").is_file()
    assert (out / "pipeline" / "demo_pipe.html").is_file()
    assert (out / "data" / "index.json").is_file()
    assert (out / "CNAME").read_text().strip() == "repository.nirs4all.org"
    index = (out / "index.html").read_text()
    assert '<link rel="canonical" href="https://repository.nirs4all.org/">' in index
    assert '<meta property="og:url" content="https://repository.nirs4all.org/">' in index
    assert "Sitemap: https://repository.nirs4all.org/sitemap.xml" in (out / "robots.txt").read_text()
    assert "<loc>https://repository.nirs4all.org/pipeline/demo_pipe.html</loc>" in (out / "sitemap.xml").read_text()
    detail = (out / "pipeline" / "demo_pipe.html").read_text()
    assert '<link rel="canonical" href="https://repository.nirs4all.org/pipeline/demo_pipe.html">' in detail
    assert '"@type":"SoftwareSourceCode"' in detail
    assert "<script>alert(1)</script>" not in detail
    assert "&lt;script&gt;" in detail


def test_seed_catalogue_is_valid(repo_root):
    """The committed seed catalogue loads and lists without error."""
    entries = n4r.list(root=repo_root)
    assert len(entries) >= 4
    ids = {e["id"] for e in entries}
    assert "snv_savgol_pls" in ids
