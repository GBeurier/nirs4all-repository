<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# nirs4all-repository — Specification

> The concrete, versioned contracts behind [`DESIGN.md`](DESIGN.md): the pipeline
> descriptor schema, the per-pipeline manifest, the cross-language `index.json`
> registry, the bundle layout, the Python public API, and the `n4a-repository` CLI.
> All schemas carry an integer `schema_version`. The current version is **1**, and the
> loader enforces a dag-ml-style compatibility window from 0.1.0: `SCHEMA_VERSION = 1`,
> `MIN_READABLE = 1`, `MIN_WRITABLE = 1`. A reader **refuses** a `schema_version` above
> `SCHEMA_VERSION` (an unknown future format) or below `MIN_READABLE`; a writer only ever
> emits `SCHEMA_VERSION`. This lets the frozen 0.1.0 contract evolve later without silent
> misreads.

## 1. Slugs, paths, and canonical JSON

- **Pipeline id / slug**: `^[a-z0-9]+(?:_[a-z0-9]+)*$`. Equal to the directory name
  `pipelines/<id>/`. Unique across the catalogue.
- **Canonical JSON** (every generated `*.json`): UTF-8, `json.dumps(..., sort_keys=True,
  indent=2, ensure_ascii=False)` + a single trailing `\n`. This makes generated files
  byte-stable so a `git diff --exit-code` freshness check is meaningful and so any
  language reproduces identical bytes.
- **Safe relative path**: a bundle file path must be relative, must not be absolute,
  must not contain `..` segments, and must not escape the bundle root. Enforced on
  read and write (the `validate_portable` admission rule).

## 2. `PipelineDescriptor` — `pipelines/<id>/descriptor.yaml` (hand-authored)

Pydantic v2 model, `schema_version: 1`. YAML on disk.

```yaml
schema_version: 1                       # int, required
id: snv_savgol_pls                      # slug, required, == directory name
name: "SNV · Savitzky–Golay · PLS"      # str, required — display name
summary: "Baseline NIRS regression: SNV, SG smoothing, 10-component PLS."  # str, required, <= 200 chars
description: |                          # str, optional — Markdown long form
  A robust regression baseline for continuous NIRS targets ...
framework: nirs4all                     # enum: nirs4all | dag-ml — required
kind: recipe                            # enum: recipe | fitted — required
task: regression                        # enum: regression | classification | multitask | clustering | other
tags: [pls, preprocessing, baseline]    # list[str], slug-ish, optional
version: "1.0.0"                         # str (PEP 440 / semver), required — pipeline version, independent of repo version
license: "CeCILL-2.1 OR AGPL-3.0-or-later"  # SPDX expression, required
created_at: "2026-06-17"                 # ISO date, required
updated_at: "2026-06-17"                 # ISO date, optional
authors:                                 # list[Author], required, >= 1
  - name: "Gregory Beurier"
    email: "gregory.beurier@cirad.fr"    # optional
    orcid: "0000-0002-..."               # optional
    affiliation: "CIRAD"                 # optional

recipe:                                  # Recipe, required
  format: nirs4all/pipeline-config       # enum (see §6): nirs4all/pipeline-config
                                         #   | dag-ml/pipeline-dsl | dag-ml/compiled-artifact
  path: pipeline.json                    # safe relative path inside the bundle (json or yaml)

artifacts:                               # list[Artifact], optional — required & non-empty iff kind == fitted
  - name: "model_bundle.n4a"
    backend: n4a                         # enum: n4a | joblib | onnx | safetensors | json | raw
    relpath: artifacts/3f9a...e1.n4a     # safe relative path; basename is the sha256 for blobs
    sha256: "3f9a...e1"                  # 64-hex, required
    size_bytes: 20480                    # int, required
    storage: inline                      # enum: inline (committed / wheel data) | release (GH Release asset)
    download_url: null                   # required iff storage == release
```

**`Artifact` ⇄ dag-ml `ArtifactRef` mapping (lossless).** The repository uses
repo-native field names, but each maps 1:1 to dag-ml's `ArtifactRef`, and the admission
rule is identical to `ArtifactRef.validate_portable()`:

| repository `Artifact` | dag-ml `ArtifactRef` | rule |
|---|---|---|
| `relpath` | `uri` | safe **relative** path (no `..`, not absolute, no root escape) |
| `sha256` | `content_fingerprint` | 64-hex, **required** |
| `backend` | `backend` | **required**; `n4a` (a nirs4all ZIP bundle, stored **opaque** — not unpacked) extends dag-ml's set (`joblib`/`onnx`/`safetensors`/`json`/`raw`) |
| `size_bytes` | `size_bytes` | int |
| `storage` / `download_url` | (repo-only) | `inline` ⇒ bytes materialised with the bundle; `release` ⇒ GH Release asset, `download_url` required |

A `backend: n4a` blob is the whole `.n4a` ZIP addressed by its outer sha256; its
*internal* structure (`manifest.json`/`pipeline.json`/`trace.json`/`artifacts/*.joblib`/
`fold_weights.json`, `BUNDLE_FORMAT_VERSION "1.0"`) is validated only by `nirs4all`'s
own `BundleLoader` at functional evaluation — never re-implemented here.

```yaml

reference:                               # Reference, optional (required to be `evaluate`-able)
  source: nirs4all-datasets              # enum: nirs4all-datasets | doi | url
  name: "rice_protein"                   # dataset name (source == nirs4all-datasets)
  doi: "10.18167/DVN1/XXXXXX"            # optional, when source == doi
  split: null                            # optional split selector

evaluation:                              # Evaluation, optional
  metric: rmse                           # str — a nirs4all metric name
  task: regression
  expected:                              # map of partition -> {value, tol}
    val:  { value: 0.118, tol: 0.02 }
    test: { value: 0.149, tol: 0.03 }
  nirs4all_version: ">=0.10,<0.11"       # version spec the metrics were produced under
  status: unvalidated                    # enum: unvalidated | validated | failed — set by `evaluate`
  validated_at: null                     # ISO datetime, set by `evaluate`

provenance:                              # Provenance, optional
  generated_by: "nirs4all 0.10.2"        # tool + version that produced the recipe/artifacts
  fingerprints:                          # framework-native identity (see DESIGN §4.3)
    config_sha256: "a1b2c3d4e5f60718"    # nirs4all 16-char config hash
    # graph_fingerprint / campaign_fingerprint / controller_fingerprint for dag-ml
  source: "nirs4all-lab/harness/exp_042" # free-form origin pointer
  notes: "..."                           # optional

governance:                              # Governance, optional (defaults shown)
  status: draft                          # enum: draft | published | deprecated
  visibility: public                     # enum: public  (only public is supported in 0.1.0)
  trust: community                        # enum: official | community | experimental
```

**Cross-field rules** (enforced by the model + `validate`):

- `kind == fitted` ⇒ `artifacts` present and non-empty; each artifact with
  `storage == release` ⇒ `download_url` present.
- `kind == recipe` ⇒ `artifacts` empty/absent.
- `evaluation` present ⇒ `reference` present.
- every `recipe.path` / `artifacts[].relpath` is a safe relative path; every artifact
  has `backend` + `sha256` (the `validate_portable` admission rule).
- `governance.status == published` ⇒ `publication_blockers()` returns empty: open
  license + ≥1 author + `provenance` present + static validation + security scan all
  pass; **and for `trust` ∈ {official, community}, also `evaluation.status ==
  validated`** (a published "tested" pipeline has been re-run against its reference).

## 3. `manifest.json` — `pipelines/<id>/manifest.json` (generated)

Content manifest / byte-identity authority. Canonical JSON. **Deterministic**: it
carries no wall-clock build time — `created_at` is copied from the descriptor (an
authored date), so regenerating it yields byte-identical output and the freshness check
holds. `files[]` lists exactly the *data files* `{descriptor.yaml, recipe, card.md,
artifacts/*}` — it never lists `manifest.json` or `ro-crate-metadata.json` (no
self-reference).

```json
{
  "schema_version": 1,
  "id": "snv_savgol_pls",
  "framework": "nirs4all",
  "kind": "recipe",
  "pipeline_version": "1.0.0",
  "generated_by": "nirs4all 0.10.2",
  "created_at": "2026-06-17",
  "fingerprints": { "config_sha256": "a1b2c3d4e5f60718" },
  "files": [
    { "relpath": "descriptor.yaml", "sha256": "…", "size_bytes": 812 },
    { "relpath": "pipeline.json",   "sha256": "…", "size_bytes": 640 },
    { "relpath": "card.md",         "sha256": "…", "size_bytes": 1190 }
  ],
  "artifacts": [
    { "relpath": "artifacts/3f9a…e1.n4a", "backend": "n4a", "sha256": "3f9a…e1",
      "size_bytes": 20480, "storage": "inline", "download_url": null }
  ]
}
```

## 4. `ro-crate-metadata.json` — `pipelines/<id>/ro-crate-metadata.json` (generated)

RO-Crate 1.1 JSON-LD. A root dataset (`@id: "./"`) whose `hasPart` lists every bundle
file as a `File` node carrying `sha256`, a `dagml:sha256` mirror, `contentSize`, and
`encodingFormat`. This is the tamper-evidence + provenance manifest, identical in shape
to dag-ml's `ro-crate-metadata.json`, so a dag-ml-aware tool reads it unchanged. The
validator recomputes SHA-256 over every listed file and refuses on mismatch.

## 5. `catalog/index.json` — the cross-language registry (generated)

The single machine contract. Canonical JSON, bundled into the wheel, served at
`/data/index.json`. `generated_at` is **deterministic** — `build` preserves the prior
value when nothing else changed, so the file only changes when content does.

```json
{
  "schema_version": 1,
  "repository": "nirs4all-repository",
  "repository_version": "0.1.0",
  "generated_at": "2026-06-17T00:00:00Z",
  "base_url": "https://repository.nirs4all.org",
  "count": 4,
  "pipelines": {
    "snv_savgol_pls": {
      "id": "snv_savgol_pls",
      "name": "SNV · Savitzky–Golay · PLS",
      "summary": "Baseline NIRS regression …",
      "framework": "nirs4all",
      "kind": "recipe",
      "task": "regression",
      "tags": ["pls", "preprocessing", "baseline"],
      "version": "1.0.0",
      "license": "CeCILL-2.1 OR AGPL-3.0-or-later",
      "authors": [{ "name": "Gregory Beurier" }],
      "descriptor": { "relpath": "descriptor.yaml", "sha256": "…", "size_bytes": 812,
                      "url": "https://repository.nirs4all.org/data/pipelines/snv_savgol_pls/descriptor.yaml" },
      "recipe": { "format": "nirs4all/pipeline-config", "relpath": "pipeline.json",
                  "sha256": "…", "size_bytes": 640,
                  "url": "https://repository.nirs4all.org/data/pipelines/snv_savgol_pls/pipeline.json" },
      "files": [ { "relpath": "card.md", "sha256": "…", "size_bytes": 1190, "backend": null,
                   "storage": "inline", "download_url": null,
                   "url": "https://repository.nirs4all.org/data/pipelines/snv_savgol_pls/card.md" } ],
      "reference": { "source": "nirs4all-datasets", "name": "rice_protein" },
      "evaluation": { "metric": "rmse", "status": "validated",
                      "expected": { "val": { "value": 0.118, "tol": 0.02 } },
                      "validated_at": "2026-06-17" },
      "fingerprints": { "config_sha256": "a1b2c3d4e5f60718" },
      "trust": "official",
      "card_url": "pipeline/snv_savgol_pls.html"
    }
  }
}
```

Every referenced file (the `descriptor`, the `recipe`, and each entry in `files`)
carries `relpath` + `sha256` + an absolute `url`. The served recipe `url` always points
at the **canonical-JSON** form (even for YAML-authored recipes), so a client never needs
the repo layout or a YAML parser — only `index.json` + the URLs in it. The
wheel-bundled copy resolves the same `relpath`s offline under
`nirs4all_repository/_catalog/`.

## 6. Recipe formats (`recipe.format`)

| value | meaning | parsed/validated as |
|---|---|---|
| `nirs4all/pipeline-config` | a `nirs4all` pipeline config — exactly one of: a **bare step list** `[step, …]`, or an object `{ "name"?, "pipeline": [step, …] }`, or `{ "name"?, "steps": [step, …] }` (`steps` is `nirs4all`'s accepted alias and is **normalised to `pipeline`** on read) | structural check: a `pipeline`/`steps` list of well-formed steps (`class`/`params`, `model`, `meta_model`, `y_processing`, `feature_augmentation`, `branch`/`merge`, `name`, generators `_or_`/`_range_`/`pick`/`count`). Identity = the canonical steps SHA-256 (16-char) computed exactly as `nirs4all.PipelineConfigs.get_hash`. Optional strict check via `nirs4all.PipelineConfigs` |
| `dag-ml/pipeline-dsl` | a `dag-ml` pipeline DSL (nirs4all-compat list/dict or canonical `PipelineDslSpec`) | structural check against the `pipeline_dsl` shape; optional strict check via dag-ml compile |
| `dag-ml/compiled-artifact` | a `CompiledPipelineArtifact` = `{ "graph": GraphSpec, "campaign_template": CampaignSpec }` | required keys present; optional strict check via dag-ml |

The recipe file is JSON or YAML (detected by extension/content). Strict, framework-level
validation is opt-in (needs the framework installed); the hermetic gate uses the
structural check so CI stays dependency-light.

## 7. Python public API (`nirs4all_repository`)

`import nirs4all_repository` is cheap (no numpy/nirs4all/dag-ml import). `__all__`:

```python
def list(*, framework=None, task=None, tag=None, kind=None, trust=None,
         root=None) -> list[dict]:
    """Return catalogue entries (from index.json) matching the filters."""

def card(name: str, *, root=None) -> dict:
    """Return the full descriptor (+ evaluation) for one pipeline. Resolves the
    descriptor local-first, else from the wheel-bundled catalogue, else by fetching
    the descriptor `url` from the index and sha256-verifying it."""

def get(name: str, *, root=None, cache_dir=None, verify=True,
        with_artifacts=False) -> "Pipeline":
    """Resolve a pipeline by name (local-first, else fetch + sha256-verify + cache).
    Fitted artifacts are downloaded only when with_artifacts=True."""

def fetch(name: str, *, root=None, cache_dir=None, verify=True,
          with_artifacts=False) -> "pathlib.Path":
    """Materialise the bundle locally and return its directory path."""

class Pipeline:
    descriptor: PipelineDescriptor
    path: pathlib.Path
    def recipe(self) -> dict: ...                 # the parsed recipe
    def to_nirs4all(self) -> dict: ...            # config ready for nirs4all.run()/predict()
    def to_dagml(self) -> dict: ...               # DSL / compiled artifact for dag-ml
    def verify(self) -> None: ...                 # recompute + check all sha256

class Settings: ...                                # root, cache_dir, base_url, allowlist
def get_settings() -> Settings: ...
__version__: str
```

**Resolution order** for `get`/`fetch` (the `nirs4all-datasets` model):

1. **local-first** — if a checkout root (cwd or `root=`) contains `pipelines/<id>/`,
   read it directly: no network.
2. **wheel-bundled** — else if the installed package carries the catalogue under
   `nirs4all_repository/_catalog/pipelines/<id>/`, read it directly: no network. This is
   the offline path for recipe pipelines.
3. **remote** — else read `index.json` (bundled or fetched from `base_url`), download
   the recipe (+ artifacts iff `with_artifacts`), SHA-256-verify, and cache under
   `~/.cache/nirs4all-repository/<id>/<recipe_sha256>/`. Caching by recipe sha256 (not
   bare id) means a changed recipe or a new pipeline version never reads a stale entry.
4. `verify=True` (default) recomputes every data-file sha256 before returning; any
   mismatch raises. `schema_version` above the supported window also raises.

The bridges (`to_nirs4all`/`to_dagml`) import the framework lazily and degrade with a
clear error if it is absent.

## 8. CLI — `n4a-repository` (Typer)

| command | purpose | heavy deps? |
|---|---|---|
| `list [--framework --task --tag --kind --trust]` | print the catalogue | no |
| `show <id>` / `card <id>` | print descriptor + evaluation | no |
| `get <id> [--with-artifacts]` | fetch to cache, print path | network |
| `add <id> --recipe FILE --framework F [...]` | scaffold `pipelines/<id>/` from a recipe | no |
| `validate [<id> | --all] [--run]` | schema + structure + checksums + security scan (`--run` also evaluates) | `--run` only |
| `scan <id>` | security scan only (class allow-list + pickle opcodes) | no |
| `build` | regenerate `manifest.json` + `ro-crate-metadata.json` + `catalog/index.json` | no |
| `site [--out site]` | render the static catalogue site | no |
| `evaluate <id>` | run against the reference dataset; compare to expected metrics; write status | nirs4all + data |
| `publish <id>` | check `publication_blockers()`; report readiness | no |

The CLI subcommands *are* the build/maintenance interface (there is no Makefile), as in
`nirs4all-datasets`.

## 9. Cross-language contract (for non-Python clients)

A client in any language consumes the repository with three primitives:

1. **GET** `https://repository.nirs4all.org/data/index.json` → parse JSON.
2. Look up `pipelines[<id>]`; for the recipe and each artifact, **GET** its `url` /
   `download_url`.
3. **Verify** the downloaded bytes against the published `sha256` before use; cache by
   sha256.

The recipe JSON is already in the target framework's native config form. No server, no
auth, no language-specific encoding — just HTTPS + SHA-256 + JSON. `schema_version`
gates compatibility (a client refuses a `schema_version` newer than it supports). This
contract is frozen at 0.1.0; the Python client is its reference implementation, and the
catalogue site's JS is a working second consumer.

## 10. Settings & environment

- `NIRS4ALL_REPOSITORY_ROOT` — path to a catalogue checkout (overrides cwd local-first).
- `NIRS4ALL_REPOSITORY_BASE_URL` — base URL for remote resolution
  (default `https://repository.nirs4all.org`).
- `NIRS4ALL_REPOSITORY_CACHE` — cache dir (default `~/.cache/nirs4all-repository`).
- `NIRS4ALL_REPOSITORY_ALLOWLIST` — comma-separated extra allowed module roots for the
  security scan. **Local developer convenience only**: the publication gate and CI
  always use the curated built-in allow-list and ignore this variable, so it can never
  widen what is published.

---

© 2026 CIRAD — nirs4all ecosystem. Documentation is licensed CC-BY-4.0.
