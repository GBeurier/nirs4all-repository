# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Pure-Python static-site renderer for ``repository.nirs4all.org``.

Reads the committed catalogue (``catalog/index.json`` + per-bundle files) and emits a
self-contained static site: a hero + filterable pipeline grid (``index.html``), one
detail page per pipeline, the ``/data/`` tree (the cross-language contract, served
verbatim), brand assets, ``CNAME``, ``.nojekyll``, ``robots.txt`` and ``sitemap.xml``.

No framework, no bundler, no heavy imports. **All authored content is HTML-escaped**;
``card.md`` is rendered through the safe Markdown subset — a malicious card cannot
inject script.
"""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any

from .._version import __version__
from ..markdown_safe import render_markdown
from ..settings import DEFAULT_BASE_URL
from ..store import CARD_FILENAME, load_index, pipeline_dir
from .assets import SCRIPT, STYLE

_GOATCOUNTER = (
    '<script data-goatcounter="https://nirs4all.goatcounter.com/count" '
    "data-goatcounter-settings='{\"path\": \"/repository\"}' "
    'async src="//gc.zgo.at/count.js"></script>'
)
_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700'
    "&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap\" rel=\"stylesheet\">"
)


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _head(title: str, description: str, base_url: str, prefix: str) -> str:
    og_image = f"{base_url}/assets/brand/og.png"
    return (
        "<!doctype html><html lang=\"en\"><head>"
        '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_esc(title)}</title>"
        f'<meta name="description" content="{_esc(description)}">'
        '<meta name="theme-color" content="#AC564A">'
        f'<meta property="og:type" content="website"><meta property="og:title" content="{_esc(title)}">'
        f'<meta property="og:description" content="{_esc(description)}">'
        f'<meta property="og:image" content="{_esc(og_image)}">'
        '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
        '<meta name="twitter:card" content="summary_large_image">'
        f'<meta name="twitter:title" content="{_esc(title)}"><meta name="twitter:image" content="{_esc(og_image)}">'
        f'<link rel="icon" type="image/svg+xml" href="{prefix}assets/brand/icon.svg">'
        f'<link rel="icon" href="{prefix}assets/brand/favicon.ico">'
        f'<link rel="apple-touch-icon" href="{prefix}assets/brand/icon-180.png">'
        f"{_FONTS}<style>{STYLE}</style></head>"
    )


def _header(prefix: str) -> str:
    return (
        '<div class="spectrum-strip"></div>'
        '<header class="site"><div class="container header-row">'
        f'<a href="{prefix}index.html"><img class="logo" src="{prefix}assets/brand/horizontal.svg" alt="nirs4all-repository"></a>'
        '<span class="pill-badge">repository</span><span class="spacer"></span>'
        '<nav><a href="https://nirs4all.org">nirs4all.org</a>'
        '<a href="https://github.com/GBeurier/nirs4all-repository">GitHub</a>'
        '<a href="https://nirs4all-repository.readthedocs.io">Docs</a></nav>'
        "</div></header>"
    )


def _footer() -> str:
    return (
        '<footer class="site"><div class="container">'
        '<div class="fam">'
        '<a href="https://nirs4all.org">nirs4all.org</a>'
        '<a href="https://formats.nirs4all.org">formats</a>'
        '<a href="https://datasets.nirs4all.org">datasets</a>'
        '<a href="https://cockpit.nirs4all.org">cockpit</a>'
        '<a href="https://github.com/GBeurier/nirs4all-repository">GitHub</a>'
        "</div>"
        f'<div class="meta">nirs4all-repository v{_esc(__version__)} · pre-configured, tested NIRS pipelines · CeCILL-2.1 OR AGPL-3.0-or-later · © 2026 CIRAD</div>'
        f"</div></footer>{_GOATCOUNTER}</body></html>"
    )


def _spark(pipeline_id: str) -> str:
    """A small deterministic inline-SVG spectral sparkline for a card."""
    seed = sum(ord(ch) for ch in pipeline_id)
    points = []
    for i in range(13):
        x = 4 + i * 3.5
        wave = (seed % (7 + i)) % 5
        y = 26 - (8 + ((seed >> i) % 12) + wave) * 0.9
        points.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(points)
    return (
        '<svg class="card-spark" width="52" height="32" viewBox="0 0 52 32" aria-hidden="true">'
        '<rect x="0.5" y="0.5" width="51" height="31" rx="8" fill="rgba(172,86,74,0.06)" stroke="rgba(172,86,74,0.2)"/>'
        f'<polyline points="{poly}" fill="none" stroke="#AC564A" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg>"
    )


def _status_badge(entry: dict[str, Any]) -> str:
    evaluation = entry.get("evaluation") or {}
    status = evaluation.get("status")
    if status == "validated":
        return '<span class="status ok">validated</span>'
    if status == "failed":
        return '<span class="status warn">eval failed</span>'
    return '<span class="status">unvalidated</span>'


def _card(entry: dict[str, Any]) -> str:
    pid = entry["id"]
    fw = entry["framework"]
    search = " ".join([pid, entry.get("name", ""), entry.get("summary", ""), *entry.get("tags", [])]).lower()
    tags_attr = " ".join(entry.get("tags", []))
    cls = "card fw-dagml" if fw == "dag-ml" else "card"
    badges = [
        f'<span class="badge fw">{_esc(fw)}</span>',
        f'<span class="badge">{_esc(entry.get("kind", ""))}</span>',
        f'<span class="badge">{_esc(entry.get("task", ""))}</span>',
        f'<span class="badge">{_esc(entry.get("trust", ""))}</span>',
        _status_badge(entry),
    ]
    return (
        f'<div class="{cls}" data-id="{_esc(pid)}" data-framework="{_esc(fw)}" '
        f'data-task="{_esc(entry.get("task", ""))}" data-kind="{_esc(entry.get("kind", ""))}" '
        f'data-trust="{_esc(entry.get("trust", ""))}" data-tag="{_esc(tags_attr)}" data-search="{_esc(search)}">'
        f'<a class="card-link" href="pipeline/{_esc(pid)}.html" aria-label="{_esc(entry.get("name", pid))}"></a>'
        f'<div class="card-head">{_spark(pid)}<div class="card-titles">'
        f'<div class="card-cat">{_esc(entry.get("task", "pipeline"))}</div>'
        f'<div class="card-name">{_esc(entry.get("name", pid))}</div></div>'
        f'<span class="card-ver">v{_esc(entry.get("version", ""))}</span></div>'
        f'<p class="desc">{_esc(entry.get("summary", ""))}</p>'
        f'<div class="badges">{"".join(badges)}</div>'
        "</div>"
    )


def _chipset(index: dict[str, Any]) -> str:
    pipelines = index.get("pipelines", {}).values()

    def dim_values(key: str) -> list[str]:
        return sorted({str(p.get(key)) for p in pipelines if p.get(key)})

    groups = []
    for dim, label in (("framework", "framework"), ("task", "task"), ("kind", "kind"), ("trust", "trust")):
        values = dim_values(dim)
        if len(values) < 2:
            continue
        chips = "".join(f'<button class="chip" data-dim="{dim}" data-val="{_esc(v)}">{_esc(v)}</button>' for v in values)
        groups.append(f'<div class="chipset" aria-label="{label}">{chips}</div>')
    return "".join(groups)


def render_index(index: dict[str, Any], base_url: str) -> str:
    pipelines = sorted(index.get("pipelines", {}).values(), key=lambda entry: entry["id"])
    n = len(pipelines)
    frameworks = len({p.get("framework") for p in pipelines})
    validated = sum(1 for p in pipelines if (p.get("evaluation") or {}).get("status") == "validated")
    cards = "".join(_card(entry) for entry in pipelines) or '<div class="empty">No pipelines yet.</div>'

    head = _head(
        "nirs4all-repository — pre-configured, tested NIRS pipelines",
        "A public, versioned repository of pre-configured, tested NIRS pipelines for nirs4all and dag-ml — loadable by name, with provenance and validation.",
        base_url,
        "",
    )
    body = (
        f"<body>{_header('')}"
        '<section class="hero"><div class="container">'
        '<span class="eyebrow">repository.nirs4all.org</span>'
        "<h1>Pre-configured, <em>tested</em> NIRS pipelines</h1>"
        '<p class="lead">A public, versioned catalogue of ready-to-run nirs4all and dag-ml pipelines — '
        "preprocessing, model and evaluation packaged with provenance, validated against reference datasets, "
        "and loadable by name from Python and across the ecosystem.</p>"
        '<div class="ctas">'
        '<a class="btn btn-primary" href="#catalogue">Browse the catalogue</a>'
        '<a class="btn btn-ghost" href="https://github.com/GBeurier/nirs4all-repository">View on GitHub</a></div>'
        '<div class="stats">'
        f'<div class="stat"><div class="num">{n}</div><div class="lbl">pipelines</div></div>'
        f'<div class="stat"><div class="num">{frameworks}</div><div class="lbl">frameworks</div></div>'
        f'<div class="stat"><div class="num">{validated}</div><div class="lbl">validated</div></div>'
        "</div></div></section>"
        '<section class="section-paper" id="catalogue"><div class="container">'
        '<div class="section-head"><h2>Catalogue</h2><p>Filter by framework, task, kind, or trust — or search.</p></div>'
        f'<div class="filters"><input type="search" id="q" placeholder="Search pipelines…" aria-label="Search">{_chipset(index)}</div>'
        f'<div class="grid">{cards}</div>'
        '<div class="empty" id="empty" style="display:none">No pipelines match these filters.</div>'
        "</div></section>"
        f"{_footer()}"
        f"<script>{SCRIPT}</script>"
    )
    return head + body


def _usage_snippet(entry: dict[str, Any], base_url: str) -> str:
    pid = entry["id"]
    py = (
        '<span class="cmt"># Python</span>\n'
        "import nirs4all_repository as n4r\n"
        f'pipe = n4r.get("{pid}")\n'
        "config = pipe.to_nirs4all()  # ready for nirs4all.run() / predict()"
    )
    recipe_url = entry["recipe"]["url"]
    sh = (
        '<span class="cmt"># any language: read the index, fetch + verify</span>\n'
        f"curl {base_url}/data/index.json\n"
        f"curl {_esc(recipe_url)}"
    )
    return f'<pre class="code">{py}</pre><pre class="code">{sh}</pre>'


def render_detail(entry: dict[str, Any], recipe_text: str, card_html: str, description: str, base_url: str) -> str:
    pid = entry["id"]
    head = _head(
        f"{entry.get('name', pid)} — nirs4all-repository",
        entry.get("summary", ""),
        base_url,
        "../",
    )
    rows = [
        ("framework", entry.get("framework", "")),
        ("kind", entry.get("kind", "")),
        ("task", entry.get("task", "")),
        ("version", entry.get("version", "")),
        ("license", entry.get("license", "")),
        ("trust", entry.get("trust", "")),
        ("tags", ", ".join(entry.get("tags", [])) or "—"),
    ]
    kv = "".join(f"<dt>{_esc(k)}</dt><dd>{_esc(v)}</dd>" for k, v in rows)

    authors = ", ".join(a.get("name", "") for a in entry.get("authors", [])) or "—"
    fingerprints = entry.get("fingerprints", {}) or {}
    fp = "".join(f'<div class="metric-row"><span>{_esc(k)}</span><span>{_esc(v)}</span></div>' for k, v in fingerprints.items()) or '<div class="metric-row"><span>—</span><span></span></div>'

    evaluation = entry.get("evaluation") or {}
    metric_rows = ""
    if evaluation:
        for partition, exp in (evaluation.get("expected") or {}).items():
            metric_rows += f'<div class="metric-row"><span>{_esc(partition)} · {_esc(evaluation.get("metric", ""))}</span><span>{_esc(exp.get("value"))} ±{_esc(exp.get("tol"))}</span></div>'
        metric_rows += f'<div class="metric-row"><span>status</span><span>{_esc(evaluation.get("status", "unvalidated"))}</span></div>'
    else:
        metric_rows = '<div class="metric-row"><span>no expected metrics</span><span></span></div>'

    reference = entry.get("reference") or {}
    ref_text = _esc(reference.get("name") or reference.get("doi") or "—") if reference else "—"

    body = (
        f"<body>{_header('../')}"
        '<section class="detail"><div class="container">'
        f'<div class="crumb"><a href="../index.html">catalogue</a> / {_esc(pid)}</div>'
        f"<h1>{_esc(entry.get('name', pid))}</h1>"
        f'<p class="lead">{_esc(entry.get("summary", ""))}</p>'
        f"{_status_badge(entry)}"
        '<div class="detail-grid"><div>'
        f'<div class="panel"><h3>Overview</h3><div class="card-md">{card_html}</div></div>'
        f'<div class="panel"><h3>Recipe</h3><pre class="code">{_esc(recipe_text)}</pre></div>'
        f'<div class="panel"><h3>Use it</h3>{_usage_snippet(entry, base_url)}</div>'
        "</div><div>"
        f'<div class="panel"><h3>Metadata</h3><dl class="kv">{kv}<dt>authors</dt><dd>{_esc(authors)}</dd><dt>reference</dt><dd>{ref_text}</dd></dl></div>'
        f'<div class="panel"><h3>Expected metrics</h3>{metric_rows}</div>'
        f'<div class="panel"><h3>Provenance</h3>{fp}</div>'
        f'<div class="panel"><h3>Download</h3><dl class="kv">'
        f'<dt>recipe</dt><dd><a href="{_esc(entry["recipe"]["url"])}">{_esc(entry["recipe"]["relpath"])}</a></dd>'
        f'<dt>descriptor</dt><dd><a href="{_esc(entry["descriptor"]["url"])}">descriptor.yaml</a></dd>'
        "</dl></div>"
        "</div></div></div></section>"
        f"{_footer()}"
    )
    _ = description
    return head + body


def build_site(root: Path, out_dir: Path, *, base_url: str = DEFAULT_BASE_URL) -> Path:
    """Render the catalogue site from *root* into *out_dir* and return *out_dir*."""
    base_url = base_url.rstrip("/")
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    (out_dir / "pipeline").mkdir()
    (out_dir / "data").mkdir()

    index = load_index(root)

    # index.html
    (out_dir / "index.html").write_text(render_index(index, base_url), encoding="utf-8")

    # data/ — the cross-language contract, served verbatim
    (out_dir / "data" / "index.json").write_text(json.dumps(index, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # detail pages + per-pipeline data tree
    for pid, entry in index.get("pipelines", {}).items():
        src = pipeline_dir(root, pid)
        recipe_rel = entry["recipe"]["relpath"]
        recipe_text = (src / recipe_rel).read_text(encoding="utf-8")
        card_path = src / CARD_FILENAME
        card_html = render_markdown(card_path.read_text(encoding="utf-8")) if card_path.is_file() else ""
        page = render_detail(entry, recipe_text, card_html, entry.get("summary", ""), base_url)
        (out_dir / "pipeline" / f"{pid}.html").write_text(page, encoding="utf-8")

        data_dir = out_dir / "data" / "pipelines" / pid
        data_dir.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            if child.is_file():
                shutil.copy2(child, data_dir / child.name)

    # brand assets
    brand_src = root / "assets" / "brand"
    if brand_src.is_dir():
        shutil.copytree(brand_src, out_dir / "assets" / "brand")

    # Pages plumbing
    (out_dir / "CNAME").write_text("repository.nirs4all.org\n", encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    (out_dir / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: " + base_url + "/sitemap.xml\n", encoding="utf-8"
    )
    _write_sitemap(out_dir, index, base_url)
    return out_dir


def _write_sitemap(out_dir: Path, index: dict[str, Any], base_url: str) -> None:
    urls = [f"{base_url}/"]
    urls += [f"{base_url}/pipeline/{pid}.html" for pid in sorted(index.get("pipelines", {}))]
    body = "".join(f"<url><loc>{html.escape(u)}</loc></url>" for u in urls)
    out_dir.joinpath("sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + body + "</urlset>\n",
        encoding="utf-8",
    )
