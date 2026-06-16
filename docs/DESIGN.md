<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# nirs4all-repository — Design

> Status: **design (0.1.0 beta)**. This document is the authoritative design and
> objectives narrative for `nirs4all-repository`. The concrete schemas, public API,
> and CLI surface are specified in [`SPECIFICATION.md`](SPECIFICATION.md); the delivery
> plan is in [`ROADMAP.md`](ROADMAP.md); the safety model is in
> [`SECURITY.md`](https://github.com/GBeurier/nirs4all-repository/blob/main/SECURITY.md).

## 1. Objectives — what this project is, and is not

`nirs4all-repository` is the public, versioned **repository of pre-configured, tested
NIRS pipelines** for the nirs4all ecosystem. It has exactly **one job**: be the place
where a pipeline — a `nirs4all` recipe or a `dag-ml` recipe, with or without fitted
artifacts — is **stored, described with provenance, validated, secured, and then
served by name** to every nirs4all library and tool, across languages, plus a public
catalogue website at `repository.nirs4all.org`.

It is the missing **remote, name-addressable layer** that neither `nirs4all` nor
`dag-ml` provides today: `nirs4all` can serialise a pipeline config and export a
fitted `.n4a` bundle, and it has a *local-disk* template library
(`nirs4all/pipeline/storage/library.py`), but there is **no remote/hub/fetch-by-name
mechanism anywhere** in the ecosystem. This repository owns that layer, and only that
layer.

### In scope

- **Store** pipelines as portable, content-addressed bundles — recipes (config only)
  or fitted (recipe + artifacts) — with full provenance.
- **Describe** each pipeline with a schema-validated descriptor + a human card +
  machine-readable provenance (RO-Crate manifest, optional W3C PROV).
- **Validate** pipelines statically (schema, structure, checksums) and functionally
  (re-run against a pinned reference dataset and compare to recorded metrics).
- **Secure** pipelines: class allow-listing for recipes, pickle-opcode scanning for
  fitted artifacts, tamper-evident checksums, trust tiers, a publication gate.
- **Serve** pipelines by name through a language-agnostic static contract
  (`index.json` + content-addressed bundles over HTTPS) consumed by the Python
  reference client and by thin clients in any language.
- **Publish** a catalogue website (`repository.nirs4all.org`) listing every pipeline,
  its description, metadata, provenance, and validation status.

### Out of scope (delegated to the layer that owns it)

- **NIRS / IO / ML logic** → `nirs4all`, `nirs4all-io`, `dag-ml`. This repo never
  re-implements parsing, dataset assembly, training, or scoring. It *invokes* them.
- **Running and ranking** pipelines as a leaderboard → `nirs4all-benchmarks` (the
  Arena). This repo is the *source of the recipes*; the benchmarks repo is *where they
  are competitively scored*.
- **Hosting reference datasets** → `nirs4all-datasets` (DOI-pinned). This repo
  *references* datasets by name/DOI; it never re-hosts dataset bytes.
- **A running API server / database.** The "API" is a static, versioned artefact
  contract (see §5). There is no backend service to operate.

This mirrors the ecosystem's load-bearing rule: **boundaries are sacred, and the lower
layer is always the single source of truth for its domain.**

### 1.1 What the 0.1.0 beta actually ships

The storage envelope and the `index.json` contract support pipelines **with or without
artifacts** from day one (`schema_version: 1`, frozen). Concretely, 0.1.0:

- implements the **recipe** path end-to-end (store → describe → validate → secure →
  serve → site), and ships a **recipe-only public seed catalogue** (small, inspectable,
  safe, hermetically testable);
- implements and tests the **fitted** path for **`storage: inline`** artifacts (a small
  content-addressed blob materialised with the bundle) so "with artifacts" is real and
  covered by tests via a fixture;
- **defers to 0.2** only the *at-scale* fitted distribution mechanics — hosting large
  artifact blobs as GitHub **Release assets** (`storage: release`) and Sigstore
  signing — because those need a published release and a networked validation job, not
  a hermetic one.

So "store pipelines with or without artifacts" is a 0.1.0 capability; only bulk
release-asset hosting is roadmap. The descriptor/index fields for `storage: release`
are specified and reserved now so the contract never breaks.

### 1.2 What a consumer does with a served pipeline

The repository serves the *artifact*. What the user does with it is theirs: a **recipe**
is handed to `nirs4all.run()` (train) or compiled by `dag-ml`; a **fitted** bundle is
handed to `nirs4all.predict()` / `explain()`. `retrain()`, `session()`, and
`generate()` are user-side operations on the loaded object, outside this repo's concern.

## 2. Design principles

1. **Recipe-first, artifact-optional.** A pipeline's primary content is its *recipe* —
   small, inspectable text (JSON/YAML). Fitted artifacts (joblib/onnx blobs) are an
   optional, opt-in addition. The default, safe object is a recipe.
2. **One envelope for both ecosystems.** A `nirs4all` `.n4a` bundle and a `dag-ml`
   `ExecutionBundle` already share a shape: *a JSON descriptor + content-addressed
   binary artifacts + a checksum manifest*. We adopt **one** bundle envelope, derived
   from dag-ml's Research Provenance Package (RO-Crate + optional PROV), for both.
3. **Content-addressed and tamper-evident.** Every file carries a SHA-256. The
   admission gate is dag-ml's `validate_portable` rule: an artifact is acceptable only
   if it declares a `backend`, a *safe relative* URI, and a `content_fingerprint`.
4. **Generated artefacts are committed and freshness-checked.** Like
   `nirs4all-datasets`, the machine index and per-pipeline manifests are generated,
   committed, and a CI `git diff --exit-code` proves they are current.
5. **The store is the source of truth; clients are thin.** Cross-language reach is a
   static `index.json` + content-addressed downloads, not N reimplementations. The
   Python client is the reference; other languages read the same contract.
6. **Cheap import, lazy heavy deps.** `import nirs4all_repository` pulls in nothing
   heavy. `numpy`/`nirs4all`/`dag-ml` are imported only on the code paths that need
   them (evaluation, bridging).
7. **Match the ecosystem, don't invent.** Pure-Python (the `nirs4all`/`nirs4all-io`
   template), ruff line-length 220, dual `CeCILL-2.1 OR AGPL-3.0-or-later` + CC-BY
   content, Sphinx/RTD docs, GitHub-Pages static site, GoatCounter analytics,
   Trusted-Publishing release, the shared `version-guard` guardrail.

## 3. Architecture overview

```
                         ┌──────────────────────────────────────────────┐
   author / CI           │              nirs4all-repository              │
   ───────────►          │                                              │
   descriptor.yaml       │  pipelines/<id>/                              │
   pipeline.json         │    descriptor.yaml   (hand-authored)          │
   card.md               │    pipeline.json     (the recipe)             │
                         │    card.md           (human card)             │
                         │    manifest.json     (generated, sha256s)     │
   `n4a-repository build`│    ro-crate-metadata.json (generated, PROV)   │
   ───────────►          │    artifacts/<sha256>.<ext>  (fitted only,    │
                         │                       hosted as Release asset)│
                         │                                              │
                         │  catalog/index.json  (generated, canonical    │
                         │                       JSON — THE contract)     │
                         └───────────────┬──────────────────────────────┘
                                         │  build / publish
                 ┌───────────────────────┼───────────────────────────────┐
                 ▼                        ▼                               ▼
   repository.nirs4all.org        GitHub Release assets         catalog/index.json
   (static site, GH Pages)        (artifact blobs, by sha256)   (served at /data/)
                 │                        │                               │
                 └────────────┬───────────┴───────────────┬──────────────┘
                              ▼                            ▼
                   Python reference client        thin clients (R / MATLAB /
                   nirs4all_repository.get(name)   JS-WASM): read index.json,
                   → to_nirs4all() / to_dagml()     fetch + verify sha256
                              │
                              ▼
                   nirs4all.run()/predict()  ·  dag-ml compile
```

### Components

- **The package `nirs4all_repository`** (src-layout, pure-Python): schema models,
  catalogue store, fetch/verify/cache, validation, security scanning, evaluation
  bridge, the static-site renderer, and the `n4a-repository` CLI.
- **The on-disk catalogue** (`pipelines/<id>/` + `catalog/index.json`): the committed
  store. Recipes are tiny text and live in git. Fitted artifact *blobs* never live in
  git; they are published as GitHub Release assets and referenced by URL + sha256.
- **The static site** (`site/`, generated): the catalogue website, deployed to GitHub
  Pages at `repository.nirs4all.org`.
- **The cross-language contract** (`catalog/index.json`): a single canonical-JSON
  registry, bundled into the wheel and served at `https://repository.nirs4all.org/data/index.json`.

## 4. Storage & provenance model

### 4.1 A pipeline on disk

Each pipeline is a directory `pipelines/<id>/` where `<id>` is a slug
(`^[a-z0-9]+(?:_[a-z0-9]+)*$`) equal to the directory name. This co-locates the
descriptor, the recipe, the card, and the generated metadata — generalising
`nirs4all`'s local `PipelineLibrary` layout (`pipeline.json` + `metadata.json` +
`README.md`) into a provenance-bearing, content-addressed bundle.

| File | Authoring | Role |
|---|---|---|
| `descriptor.yaml` | hand-authored | the `PipelineDescriptor` (schema-versioned, Pydantic-validated). The unit of catalogue membership. |
| `pipeline.json` / `pipeline.yaml` | hand-authored | the **recipe** — a `nirs4all` pipeline config or a `dag-ml` pipeline DSL / compiled artifact. |
| `card.md` | hand-authored | a human-readable card (Markdown) rendered into the site. |
| `manifest.json` | generated | content manifest: `schema_version`, per-file `sha256` + `size_bytes`, fingerprints, framework/tool versions, `created_at`. |
| `ro-crate-metadata.json` | generated | RO-Crate 1.1 manifest — per-file `sha256` (+ `dagml:sha256` mirror), `contentSize`, `encodingFormat`; the tamper-evidence + provenance layer. |
| `lineage.prov.jsonld` | generated (optional) | W3C PROV JSON-LD, for fitted pipelines that carry training lineage. |
| `artifacts/<sha256>.<ext>` | generated, **not in git** | content-addressed fitted artifact blobs (joblib/onnx/...), published as Release assets. |

This is exactly the dag-ml **Research Provenance Package** shape applied uniformly:
`descriptor(s) + artifacts/<sha256> + ro-crate-metadata.json`, with `validate_portable`
as the admission gate. A `nirs4all` `.n4a` ZIP maps to the *fitted* layer (it already
is a manifest + `artifacts/*.joblib`); a config-only recipe maps to the *recipe* layer.

### 4.2 The two pipeline kinds

- **`recipe`** — config only. The recipe is committed text. No binary blobs. Fully
  inspectable and safe. This is the seed content for 0.1.0.
- **`fitted`** — recipe + fitted artifacts. The recipe is committed; each artifact
  blob is content-addressed (`artifacts/<sha256>.<ext>`) and declared in the descriptor
  with `backend`, `relpath`, `sha256`, `size_bytes`, `storage`, and (for `release`) a
  `download_url`. Two storage modes:
  - **`inline`** — a small blob materialised with the bundle (committed in git or
    bundled as wheel package data). Validated and scanned *hermetically* (the bytes are
    present). Used by the test fixture and small official artifacts.
  - **`release`** — a large blob hosted as a GitHub **Release asset**, excluded from
    git. Validated and scanned only by the *networked* release-asset job (it must be
    downloaded first). 0.2 milestone.

A nirs4all `.n4a` bundle is itself a ZIP (`manifest.json` + `pipeline.json` +
`trace.json` + `artifacts/*.joblib` + `fold_weights.json`, `BUNDLE_FORMAT_VERSION`
"1.0"). The repository stores it **opaquely** — as one content-addressed blob with
`backend: n4a` — and does **not** unpack or re-validate its internal structure: that is
`nirs4all`'s job (the boundary rule). The internal format is exercised only at
functional evaluation, when `nirs4all`'s own `BundleLoader` opens it.

### 4.3 Identity & fingerprints

- The pipeline **id** is the directory slug and the primary key.
- The **recipe fingerprint** reuses each framework's native identity:
  `nirs4all` config SHA-256 (canonical `json.dumps(steps, sort_keys, separators=(",",":"))`,
  truncated 16 chars — matching `PipelineConfigs.get_hash`); for `dag-ml`, the
  `graph_fingerprint` / `campaign_fingerprint` / `controller_fingerprint` triple.
- Artifact blobs are addressed by full SHA-256 (`content_fingerprint`).
- `index.json` indexes on `id` and exposes all fingerprints so a client can verify the
  recipe it received matches the one it asked for.

### 4.4 The generated registry — `catalog/index.json`

A single **canonical-JSON** file (UTF-8, `sort_keys=True`, 2-space indent, single
trailing newline — the ecosystem convention) keyed by pipeline id. It is the
machine/cross-language contract, served at `/data/index.json`. Its schema is in
[`SPECIFICATION.md`](SPECIFICATION.md). Each entry carries, for the descriptor, the
recipe, and every file, both an offline `relpath` and an absolute `url`, plus a
`sha256` — so a client never needs to know the repo layout, and `card()`/`get()` can
verify exactly what they fetched.

**Offline resolution** is real: the wheel bundles, as package data, both
`catalog/index.json` *and* the per-pipeline text (`descriptor.yaml`, the recipe, the
card) under `nirs4all_repository/_catalog/`. So `pip install nirs4all-repository` then
`get(name)` resolves any **recipe** pipeline with no network; only `storage: release`
artifact blobs require a download.

The index is regenerated by `n4a-repository build` and CI fails if it drifts
(`git diff --exit-code`). **`build` is deterministic** — it embeds no wall-clock build
time (dates come from authored descriptor fields) and preserves `index.json`'s
`generated_at` when nothing else changed — so the freshness check is stable.

### 4.5 Where bytes live (three tiers)

Mirrors `nirs4all-datasets`' three-tier storage:

1. **git** — descriptors, recipes, cards, generated manifests + index, and any
   `storage: inline` artifact blobs (all small).
2. **GitHub Release assets** — large `storage: release` fitted artifact blobs,
   content-addressed by sha256 (0.2).
3. **local cache** — a content-addressed OS cache
   (`~/.cache/nirs4all-repository/<id>/<recipe_sha256>/`) holding verified downloads.
   Keying by recipe sha256 (not bare id) means different pipeline versions never
   collide and a changed recipe is auto-refetched. Recipes resolve with no network when
   the package is installed (bundled catalogue) or when running inside the checkout
   (local-first).

**Checksum coverage (explicit, to avoid self-reference).** A bundle's *data files* are
`{descriptor.yaml, the recipe, card.md, artifacts/*}`. `manifest.json` lists the sha256
of exactly those data files; the two generated manifests (`manifest.json`,
`ro-crate-metadata.json`) are **not** hashed into their own file sets. `verify()`
recomputes the data-file digests and refuses on any mismatch; the manifests' own
integrity is asserted by the committed-and-freshness-checked `build` (regenerating them
must reproduce byte-identical files).

## 5. Cross-language serving — the static contract

The "cross-language API" is **not** a running server. It is a versioned static
artefact contract — the same model `nirs4all-datasets` uses to reach R/MATLAB/WASM:

1. **`index.json`** — the registry. Any language fetches it from
   `https://repository.nirs4all.org/data/index.json` (or reads the wheel-bundled copy).
2. **Bundles by name** — for a given id, the index gives the recipe URL/relpath and any
   artifact `download_url`s, each with a `sha256`. A client downloads, verifies the
   sha256, and caches.
3. **Recipe → framework** — the recipe is already in each framework's native config
   form, so handing it to `nirs4all.run()/predict()` or `dag-ml` compile needs no
   translation.

**Served recipes are always canonical JSON.** A recipe may be *authored* as YAML for
human convenience, but `build` emits a canonical-JSON form of every recipe into the
served/bundled `data/` tree and the index URLs point at the JSON. So a non-Python
client needs only HTTP + SHA-256 + a JSON parser — never a YAML parser. (YAML is an
authoring convenience, never part of the wire contract.)

The **Python reference client** implements all of this (`get`/`list`/`card`/`fetch` +
`to_nirs4all()`/`to_dagml()` bridges). Other languages need only: HTTP GET + SHA-256 +
JSON parse — a contract documented in [`SPECIFICATION.md`](SPECIFICATION.md §"Cross-language
contract"). The catalogue site itself is a first cross-language consumer: its
client-side JS fetches `index.json` and renders the catalogue, proving the contract is
usable from a non-Python runtime. Full R/MATLAB/WASM client *packages* are roadmap
(post-0.1.0); the contract they will consume is frozen at 0.1.0.

## 6. Validation & security

Two distinct guarantees, two distinct gates.

### 6.1 Static validation (hermetic — the CI gate)

No network, no heavy deps — only the committed text and any `inline` blob. Run on every
push/PR:

- Each `descriptor.yaml` is a schema-valid `PipelineDescriptor`; `id` equals the
  directory name and is unique; `schema_version` is within the supported
  min-readable/min-writable window (§6.4).
- The recipe parses (JSON/YAML) and is *structurally* a valid `nirs4all` config (a
  `pipeline`/`steps` list of well-formed steps) or a `dag-ml` DSL/compiled artifact.
- The per-pipeline `manifest.json` data-file checksums verify against the bytes on disk
  (tamper-evidence); any `inline` artifact blob is present and its sha256 matches.
- The security scan passes (§6.3) — class allow-list for recipes; pickle-opcode scan
  for any present (`inline`) artifact blob.
- `catalog/index.json` and all generated manifests are current and deterministic
  (`build` then `git diff --exit-code`).

`storage: release` artifact blobs are not present here and are covered by §6.1b.

### 6.1b Release-asset validation (networked — on publish / opt-in)

When a fitted pipeline ships `release` blobs, a separate job (not the hermetic gate)
downloads each asset over HTTPS, verifies its sha256 against the descriptor, and runs
the pickle-opcode scan on the downloaded bytes before the pipeline may be marked
`published`. Download policy reuses `nirs4all-datasets`' rule: HTTPS only, sha256
verified before use, credentials never replayed across a redirect.

### 6.2 Functional evaluation (heavy — separate job / local)

Needs `nirs4all` + a pinned reference dataset (from `nirs4all-datasets`). Not part of
the hermetic unit gate; runs as an opt-in CI job and locally via `n4a-repository
evaluate`:

- Resolve the bundle, fetch the reference dataset by name/DOI.
- `nirs4all.run(recipe, dataset)` (recipe kind) or
  `nirs4all.predict(model=<fitted>, data=<reference>)` (fitted kind).
- Compute the recorded metric and compare to `evaluation.expected` within tolerance.
- Record `evaluation.status` (`validated` / `failed`) + timestamp into the descriptor.

This is the "tested pipelines" promise — and it is exactly the hand-off the
`nirs4all-benchmarks` Arena will reuse to *score* the same recipes.

### 6.3 Security model

Recipes reference arbitrary Python classes (`"class": "sklearn..."`) and fitted
artifacts are pickle/joblib blobs — both are code-execution vectors. The stance:

- **Recipe class allow-list.** `scan_config` walks the recipe, extracts every `class`
  reference, and rejects any whose top-level module is not in a **curated** allow-list
  (`sklearn`, `scipy`, `numpy`, `nirs4all`, `dag_ml`, `aom_nirs`, …). Blocks config-borne
  injection (`os.system`, `builtins.eval`, …). The `NIRS4ALL_REPOSITORY_ALLOWLIST` env
  override is a **local developer convenience only** — it is ignored by the publication
  gate and CI, which always use the curated list, so it can never widen what ships.
  (Exact, per-class allow-listing is a 0.2 hardening.)
- **Pickle-opcode scan.** For fitted blobs, `pickletools.genops` enumerates opcodes;
  any `GLOBAL`/`STACK_GLOBAL` importing outside the allow-list, or a known-dangerous
  callable (`os`, `posix`, `subprocess`, `builtins.eval/exec`, `nt`, `socket`, …), is
  flagged. This is a *heuristic safety net*, not a sandbox — documented as such in
  [`SECURITY.md`](https://github.com/GBeurier/nirs4all-repository/blob/main/SECURITY.md).
- **Tamper-evidence.** Per-file sha256 in the manifest + RO-Crate; `verify()` recomputes
  the data-file digests and refuses on mismatch. Downloads are HTTPS-only and
  sha256-verified before use; credentials are never replayed across a redirect.
- **Trust tiers.** `official` (built + functionally validated by repo CI), `community`
  (submitted, functionally validated), `experimental` (unvalidated). Loading fitted
  artifacts is opt-in (`with_artifacts=True`) and surfaces the tier; the API/CLI warn
  before any pickle is unpickled.
- **Publication gate** (`publication_blockers`, like `nirs4all-datasets`): a pipeline may
  be `status: published` only with an open license, ≥1 author, `provenance` present,
  and passing static validation + security scan. For `trust: official` / `community` it
  **additionally requires `evaluation.status == validated`** — so a "published, tested"
  pipeline really has been re-run against its reference dataset. `experimental` pipelines
  may publish unvalidated but are labelled as such everywhere.

### 6.4 Schema versioning & migration gate (now, not deferred)

Every contract (`PipelineDescriptor`, `manifest.json`, `catalog/index.json`) carries an
integer `schema_version`. From 0.1.0 the loader enforces a dag-ml-style gate:
`SCHEMA_VERSION = 1`, `MIN_READABLE = 1`, `MIN_WRITABLE = 1`. A reader refuses a
`schema_version` above `SCHEMA_VERSION` (a future, unknown format) or below
`MIN_READABLE`; a writer only emits `SCHEMA_VERSION`. This means the frozen 0.1.0
contract can evolve later without silent misreads — exactly the forward-compat model
`dag-ml` uses for its `ExecutionBundle`.

### 6.5 Provenance formats (explicit scope)

The stored provenance layer is **RO-Crate 1.1** (the checksum + lineage manifest,
mandatory) plus **optional W3C PROV JSON-LD** for fitted pipelines carrying training
lineage. **OpenLineage is intentionally excluded** from the stored contract: it is a
*run-event* format describing an execution, whereas this repository stores *recipes and
fitted bundles*, not runs. dag-ml emits OpenLineage at execution time; re-emitting it
here would duplicate a concern that belongs to the runner (`nirs4all-benchmarks` / the
execution engine), not the catalogue.

## 7. The catalogue website (`repository.nirs4all.org`)

A static site, generated by a pure-Python renderer (`nirs4all_repository.site`) from
the committed catalogue — the `nirs4all-datasets` `build_site` pattern. It reuses the
**nirs4all.org visual system** verbatim — the warm-paper canvas, the teal-led ecosystem
palette (`#0d9488` / `#0f766e` / `#06b6d4`), IBM Plex Sans / Inter / JetBrains Mono, the
eco-card grid, and the animated spectral strip — so the subdomain is visually
indistinguishable from its siblings. The repository's own brand mark (the horizontal
logo) leads the hero. It renders:

- a landing/hero led by the horizontal brand logo, with a catalogue summary;
- a filterable grid of pipeline cards (framework, task, tags, kind, trust, validation
  status);
- one detail page per pipeline (description, recipe preview, metadata, provenance,
  expected metrics, download/usage snippets in Python and the cross-language contract);
- `/data/index.json` (the contract) copied verbatim for client consumption.

No framework, no bundler, no dataset/heavy imports in the renderer — inline SVG charts,
brand assets copied in. Deployed to GitHub Pages via
`configure-pages`/`upload-pages-artifact`/`deploy-pages` with a committed
`CNAME = repository.nirs4all.org`, `.nojekyll`, and the GoatCounter embed
(`path: "/repository"`).

**Site safety (no stored XSS).** All authored content is treated as untrusted: the
renderer HTML-escapes every descriptor field, and `card.md` is converted by a *minimal,
safe* Markdown renderer that escapes raw HTML and supports only a fixed subset
(headings, paragraphs, lists, emphasis, inline/blocks of code, and links whose `href` is
restricted to `http(s):`/`mailto:`). Recipe previews are HTML-escaped text inside
`<pre>`. No authored bytes ever reach the page as live HTML — so a malicious submitted
card cannot inject script.

## 8. Quality bar (the green gate)

Matches the ecosystem Python siblings (`ruff` + `mypy` + `pytest`), plus the
catalogue-freshness check:

```bash
ruff check .                                   # lint (line-length 220, py311)
mypy src/nirs4all_repository                   # types
n4a-repository validate --all                  # every descriptor schema/structure/security
n4a-repository build && git diff --exit-code   # generated index/manifests are current
pytest -m "not network and not evaluate"       # hermetic unit tests
```

Functional evaluation (`pytest -m evaluate` / `n4a-repository evaluate`) and live
downloads (`-m network`) run out of the hermetic gate. Docs build under Sphinx with
the standard ecosystem extension set; the public surface carries Google-style
docstrings and a `py.typed` marker.

## 9. Relationship to the rest of the ecosystem

- **`nirs4all`** — the recipe target and the evaluation engine. Recipes are expressed
  against its public pipeline surface; `to_nirs4all()` hands them to `run()/predict()`.
- **`dag-ml`** — the second recipe target and the provenance model. Recipes may be
  dag-ml DSLs / compiled artifacts; the bundle envelope is dag-ml's RPP shape.
- **`nirs4all-datasets`** — the reference-dataset source for functional evaluation
  (by name/DOI). Never re-hosted here.
- **`nirs4all-benchmarks`** — consumes these recipes to score and rank them. This repo
  is the *source*; benchmarks is the *Arena*.
- **`nirs4all-studio` / `nirs4all-web` / lite bindings** — consumers of the static
  contract: pick a pre-configured pipeline by name from the UI or a binding.
- **`nirs4all-org`** — the umbrella landing page; its `repository` ecosystem card links
  here. **`nirs4all-cockpit`** — already tracks this repo's release/health and gains a
  `pages` target once the site is live.

---

© 2026 CIRAD — nirs4all ecosystem. Documentation is licensed CC-BY-4.0.
