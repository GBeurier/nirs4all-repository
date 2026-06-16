<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/brand/horizontal-dark.svg">
    <img alt="nirs4all-repository" src="assets/brand/horizontal.svg" width="440">
  </picture>
</p>

# nirs4all-repository

> **Status: 0.1.0 beta.** The storage envelope and the cross-language `index.json`
> contract are frozen at `schema_version: 1`. Catalogue website:
> **[repository.nirs4all.org](https://repository.nirs4all.org)**.

The public, versioned **repository of pre-configured, tested nirs4all pipelines** —
ready-to-run recipes (preprocessing → model → evaluation) stored with provenance,
validated against reference datasets, and loadable **by name** instead of rebuilt by
hand. It is the remote, name-addressable layer the ecosystem otherwise lacks.

Part of the [nirs4all ecosystem](https://github.com/GBeurier/nirs4all-ecosystem).

## What it does

- **Store** pipelines — `nirs4all` recipes or `dag-ml` recipes, **with or without**
  fitted artifacts — as portable, content-addressed bundles with full provenance.
- **Validate** them statically (schema, structure, checksums) and functionally (re-run
  against a pinned reference dataset and compare to recorded metrics).
- **Secure** them — recipe class allow-listing, pickle-opcode scanning, SHA-256
  tamper-evidence, trust tiers, and a publication gate.
- **Serve** them by name through a language-agnostic static contract (a canonical-JSON
  `index.json` + content-addressed bundles over HTTPS) consumed by the Python reference
  client and thin clients in any language.
- **Publish** a catalogue website listing every pipeline, its metadata, provenance, and
  validation status.

## Install & use

```bash
pip install nirs4all-repository
```

```python
import nirs4all_repository as n4r

n4r.list(framework="nirs4all")        # browse the catalogue
pipe = n4r.get("snv_savgol_pls")      # resolve by name (local → bundled → remote, sha256-verified)
config = pipe.to_nirs4all()           # hand to nirs4all.run() / predict()
```

The `n4a-repository` CLI is the maintenance interface
(`list` / `show` / `get` / `add` / `validate` / `scan` / `build` / `site` / `evaluate` /
`publish`).

## How a pipeline is stored

Each pipeline is a directory `pipelines/<id>/`:

| File | Role |
|---|---|
| `descriptor.yaml` | the schema-validated descriptor (the unit of catalogue membership) |
| `pipeline.json` | the **recipe** — a nirs4all config or a dag-ml DSL |
| `card.md` | a human-readable card (rendered into the site) |
| `manifest.json` | generated content manifest (per-file SHA-256) |
| `ro-crate-metadata.json` | generated RO-Crate provenance + tamper-evidence manifest |
| `artifacts/<sha256>` | content-addressed fitted artifact blobs (fitted pipelines only) |

The generated `catalog/index.json` is the single cross-language registry, served at
`/data/index.json` and bundled into the wheel for offline resolution. The envelope is
dag-ml's Research-Provenance-Package shape, so one format serves both ecosystems.

See [`docs/DESIGN.md`](docs/DESIGN.md), [`docs/SPECIFICATION.md`](docs/SPECIFICATION.md),
and [`docs/ROADMAP.md`](docs/ROADMAP.md). Security model: [`SECURITY.md`](SECURITY.md).

## Relationship to the rest of the ecosystem

- Recipes are expressed against the public **nirs4all** pipeline surface (or the
  **dag-ml** DSL) and executed by their engines; this repo does **not** re-implement
  NIRS, IO, or ML logic.
- They are scored and ranked in **nirs4all-benchmarks**; this repo is the *source of the
  recipes*, the benchmarks repo is *where they are run and ranked*.
- Reference datasets come from **nirs4all-datasets** (by name / DOI); never re-hosted here.

## Development (green gate)

```bash
ruff check .
mypy src/nirs4all_repository
n4a-repository validate --all
n4a-repository build && git diff --exit-code   # generated artifacts are current
pytest -m "not network and not evaluate"
```

## License

Pipeline **code / configurations** are dual-licensed open-source —
**`CeCILL-2.1 OR AGPL-3.0-or-later`**. The copyleft terms permit commercial use; an
optional **commercial license** is available for proprietary/closed-source use that
cannot meet the copyleft obligations (contact <nirs4all-admin@cirad.fr>). Bundled
**content** (cards, metadata, the website) is **CC-BY-4.0**. See
[`LICENSING.md`](LICENSING.md) and [`LICENSES/`](LICENSES/).
