<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# nirs4all-repository — Specification

> The concrete, versioned contracts behind [`DESIGN.md`](DESIGN.md): the pipeline
> descriptor schema, the per-pipeline manifest, the cross-language `index.json`
> registry, the bundle layout, the Python public API, and the `n4a-repository` CLI.
> Descriptors, manifests and indexes carry an integer `schema_version`. The current version is **1**, and the
> loader enforces a dag-ml-style compatibility window from 0.1.0: `SCHEMA_VERSION = 1`,
> `MIN_READABLE = 1`, `MIN_WRITABLE = 1`. A reader **refuses** a `schema_version` above
> `SCHEMA_VERSION` (an unknown future format) or below `MIN_READABLE`; a writer only ever
> emits `SCHEMA_VERSION`. This lets the frozen 0.1.0 contract evolve later without silent
> misreads.

## 1. Slugs, paths, and canonical JSON

- **Pipeline id / slug**: `^[a-z0-9]+(?:_[a-z0-9]+)*$`. Equal to the directory name
  `pipelines/<id>/`. Unique across the catalogue.
- **Canonical JSON** (derived manifests, RO-Crate metadata and index): UTF-8, `json.dumps(..., sort_keys=True,
  indent=2, ensure_ascii=False, allow_nan=False)` + a single trailing `\n`. Values must
  have text object keys and JSON scalars only; non-finite numbers are refused. This makes generated files
  byte-stable so a `git diff --exit-code` freshness check is meaningful and so any
  language reproduces identical bytes.
- **Recipe and preset snapshot JSON**: the same strict scalar/key rules, UTF-8 and
  two-space indentation, but **without sorting keys**. Preserve insertion order
  recursively: named branch mappings can carry meaningful order. Metadata
  canonicalization must not rewrite authored recipes or imported snapshots.
- **Safe relative path**: a bundle file path must be relative, must not be absolute,
  must not contain `..` segments, and must not escape the bundle root. Enforced on
  read and write (the `validate_portable` admission rule).

## 2. `PipelineDescriptor` — `pipelines/<id>/descriptor.yaml` (hand-authored)

Pydantic v2 model, `schema_version: 1`. YAML on disk.

Framework and recipe format must belong to the same owner: `nirs4all` accepts
only `nirs4all/pipeline-config`; `dag-ml` accepts only `dag-ml/pipeline-dsl` or
`dag-ml/compiled-artifact`. Descriptor admission rejects every other pairing before
scanning, publication, catalogue generation or strict framework parsing. A claimed
DAG format cannot enable DAG label exemptions for a nirs4all framework handoff.

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
  path: pipeline.json                    # safe relative path inside the bundle (.json only)

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
carries `relpath` + `sha256` + an absolute `url`. The served recipe `url` points
at the admitted **strict JSON file**, copied byte for byte. Readers, scaffold, and
catalogue generation refuse non-`.json` recipe files; `build` does not convert YAML.
Scaffold serializes the parsed JSON tree without sorting, preserving its shape,
every key and recursive mapping order. Clients need only `index.json` + its URLs and a JSON parser. The
wheel-bundled copy resolves the same `relpath`s offline under
`nirs4all_repository/_catalog/`.

## 6. Recipe formats (`recipe.format`)

| value | meaning | parsed/validated as |
|---|---|---|
| `nirs4all/pipeline-config` | a bare step list, or an object containing exactly one of `pipeline` and `steps`; both aliases together are refused even when equal | structural step checks only; list/alias shape, root fields and nested values are preserved. The legacy 16-character `config_sha256` covers steps only and is not a complete recipe identity or guaranteed framework hash. Optional strict check via `nirs4all.PipelineConfigs` |
| `dag-ml/pipeline-dsl` | a declared dag-ml DSL list or object | non-empty list/object check only; Repository does not compile it |
| `dag-ml/compiled-artifact` | a declared compiled artifact containing `graph` and `campaign_template` | required root keys present only; Repository does not validate graph semantics or replay |

Recipe files must be strict JSON, including parsed values: duplicate object keys,
non-text keys, non-JSON scalars and non-finite numbers (including `Infinity`, `NaN`
and overflow such as `1e999`) are refused. YAML source transport in the preset import
script is separate: variants must be representable as JSON without coercion, and
only the variant's root `format` transport marker is removed. No semantic conversion
or lowering occurs. Site parity compares the whole variant minus that marker,
including scalar types and mapping insertion order. Every source variant must have
a repository mapping; an unmapped variant is refused even if rendered-card checksums
have been refreshed. Duplicate YAML source keys are refused before any import writes
or source-git query.

Strict framework checks are opt-in and report warnings; structural acceptance is
not proof that a runtime will execute the recipe. Security scanning is deliberately
separate from contextual dependency observations. It examines import-shaped strings
and native `n4m:`/`n4m.` references throughout **all step subtrees**, including nested
lists, params.func, model.params.estimator, finetune_params, train_params, merge,
meta_model and sample_augmentation.transformers. A parameter key named `metadata`,
`description`, `provenance`, `name` or `id` grants no exemption: owners may deserialize
its values. Unknown paths with executable-looking strings are conservatively refused
unless their module root is allowlisted.

Only root provenance/name/description data, DAG-ML step names, and known structural
DAG root/graph/node identifiers, seed labels and edge node references are excluded
from bare-string detection. Explicit `class`, `function`, `instance` and `enum`
descriptors remain inspected even inside excluded metadata containers. Non-identifying
numeric/version strings such as `1.2` are not import references. A bare `spectra.csv`
inside params **can be refused** as an uncertain import-shaped value; the same value
in root provenance is metadata. No metadata-looking arbitrary parameter subtree is
declared safe. This is a heuristic allow-list check, not a sandbox or execution
authorization, and it does not resolve dynamic code or indirect imports.
For nirs4all, an import-shaped `name` on a class step, an external model step or a
nested model is scanned just like other step strings: owner serialization can import
it before execution. Plain display names such as `My step` remain ordinary strings.
The root name/description exemptions remain unchanged. Strict framework validation
is invoked only after all static errors and security findings are absent; rejected
recipes must never reach `PipelineConfigs` through `validate --strict`. A clean
static scan still permits imports from allowlisted roots during an opt-in strict
check and is not a sandbox. DAG-ML display exemptions do not qualify cross-routing
a DAG-ML recipe through the nirs4all parser.
Both `n4m:` role references and `n4m.` aliases are explicitly refused by the static
publication scan as unqualified owner namespaces; Repository does not expand them
or reinterpret them as Python packages.

### Derived execution requirements

`manifest.json`, each index entry, and `Pipeline.execution_requirements()` expose
the same derived block, specified by
[`execution-requirements.v1.schema.json`](../contracts/execution-requirements.v1.schema.json):

```json
{
  "schema": "nirs4all-repository.execution-requirements.v1",
  "framework": "nirs4all",
  "recipe_format": "nirs4all/pipeline-config",
  "python_module_roots": ["nirs4all", "sklearn"],
  "unknown": ["package_versions", "execution_profiles", "operations", "artifact_versions", "python_dependencies"]
}
```

Framework and recipe format come from the validated descriptor; roots are sorted,
unique import-shaped references in explicit component/recipe-node contexts:
class/function/instance/enum descriptors, bare steps and DSL/compiled operator
descriptors (including ref/type/callable). Ordinary dotted parameter and metadata
strings do not add roots. This contextual observation traversal does **not** limit
the conservative security scan described above. Roots are not resolved
distribution names or an exhaustive dependency list. `python_dependencies` is
**always unknown**, including when roots are empty: no direct reference detected
does not mean no dependency. Indirect imports (such as a model factory importing
torch), symbolic/host operators, aliases and dynamically supplied callables are not
dependency-resolved. No framework label is translated into an inferred package.
The API
recomputes the block from descriptor and recipe, so it also works for materialized
remote bundles without a manifest. Descriptors remain v1 with `extra=forbid`;
`card()` returns the original validated descriptor without injecting requirements.
These observations are additive manifest/index metadata, not a new descriptor field.
Local and remote index readers validate every present requirements block, rejecting
unknown schemas, extra fields (including claimed execution statuses), invalid roots,
missing unknown dimensions and framework/format mismatches. Downloaded observations
are checked against the actual descriptor/recipe. Existing manifests similarly check
schema version and present observations against their content. Older metadata with
no requirements block remains unqualified; missing data is not converted into a
support claim. This v1 addition was corrected before publication to include
dependency-coverage uncertainty.

Unknown means **unqualified**, not unsupported. No owner/package version, runtime
profile, operation, language/platform support, or artifact version has been established
for these recipes. Installing the optional integration extra or parsing a recipe
does not establish any of them. Core's owner vocabulary includes `native-workflow@1`,
`native-conformal@1` and `compile`, `fit`, `predict`, `import`, `export`; those profiles
describe native content such as `nirs4all.native-pipeline.v1`, not this catalogue's
`nirs4all/pipeline-config` recipes. Do not assign them based on matching class names.
Future qualification must cite the actual owner, owner version, versioned profile,
operation, artifact/content version and evidence; it needs a separate contract change.

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

# Provider-facing entry points - explicit `*_pipeline` names for nirs4all-core /
# nirs4all-ui / nirs4all-providers clients. Same read-only semantics and
# signatures as the catalogue-native functions; frozen as part of the 0.1.0 API.
def get_pipeline_list(*, framework=None, task=None, tag=None, kind=None,
                      trust=None, root=None) -> list[dict]: ...
def get_pipeline(name: str, *, root=None, cache_dir=None, verify=True,
                 with_artifacts=False) -> "Pipeline": ...
def get_bundle(name: str, *, root=None, cache_dir=None, verify=True,
               with_artifacts=False) -> "pathlib.Path": ...

class Pipeline:
    descriptor: PipelineDescriptor
    path: pathlib.Path
    def recipe(self) -> dict | list: ...          # exact parsed, structurally valid tree
    def execution_requirements(self) -> dict: ... # derived observations and explicit unknowns
    def to_nirs4all(self) -> dict | list: ...     # exact tree or explicit refusal
    def to_dagml(self) -> dict | list: ...        # exact tree; owner validates compilation
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

The bridges do not import or execute frameworks. `to_nirs4all()` refuses root keys
outside `pipeline`/`steps`, `random_state`, `name`, `description` with `BridgeError`,
because downstream config readers can discard other fields. The display fields
are explicitly allowed even where runtimes ignore them. Use `recipe()` to retrieve
the complete admitted tree. This whitelist is not a claim that all nested constructs
or parameters can execute; compiler/runtime adapters must qualify them or refuse.

**Provider-facing entry points (get-pipeline-list / get-pipeline).** The repository is a
preset/pipeline catalogue first, so custom apps built on `nirs4all-core` + `nirs4all-ui`
(directly or through `nirs4all-providers`) can address it with explicit `*_pipeline`
names: `get_pipeline_list()`, `get_pipeline()`, and `get_bundle()`. These names are the
canonical provider-facing contract for Python clients. They forward every keyword
argument unchanged and return the same objects as the catalogue-native APIs; they add
**no** new behaviour and never widen the read-only, static-index semantics. They are part
of `__all__` and frozen at 0.1.0, so a client can pin to the catalogue-native or
provider-facing name. Non-Python clients use the language-agnostic `index.json` contract
in Section 9 directly.

## 8. CLI — `n4a-repository` (Typer)

| command | purpose | heavy deps? |
|---|---|---|
| `list [--framework --task --tag --kind --trust]` | print the catalogue | no |
| `show <id>` / `card <id>` | print descriptor + evaluation | no |
| `get <id> [--with-artifacts]` | fetch to cache, print path | network |
| `add <id> --recipe FILE --framework F [...]` | scaffold `pipelines/<id>/` from a recipe | no |
| `validate [<id> | --all] [--strict]` | schema + structure + checksums + security scan; `--strict` adds opt-in nirs4all parsing warnings | `--strict` only |
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

The JSON is stored recipe content, not a compiled execution plan. Consumers must
preserve its whole tree or explicitly refuse; they must not infer execution support
from task/framework labels, static acceptance, or missing requirements. Older indexes
without `execution_requirements` provide no qualification information. Unknown
requirements do not mean unsupported. The Python local and remote index readers refuse
missing, non-integer, older and future `schema_version` values outside the supported
window. Foreign-language clients must enforce the same window, check the requirements
schema, and obtain profile/operation/artifact and owner-version evidence before making
execution claims. The existing v1 export names and signatures remain frozen; this
additive metadata does not establish cross-language numerical parity.

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

## Bounded Python descriptor reader and local project service

The owning descriptor reader now shares `store.parse_descriptor_bytes` and
`store.load_descriptor_bytes` between local files and the remote `card()` path.
Before any unsafe YAML construction it enforces 1 MiB of strict UTF-8, depth 32 and
20000 events. UTF-8 BOM is accepted. It refuses anchors, aliases, merge keys, every
explicit tag (including `!!str`, `!!binary`, `!!set` and non-specific `!`), sexagesimal
numeric scalars, duplicate keys, nonfinite floats (including overflow) and unencodable
strings. Parser/construction failures do not echo input or chain YAML diagnostics.
`DescriptorSyntaxError(CatalogError).code` is one of:

- `descriptor_too_large`, `descriptor_not_utf8`, `descriptor_yaml_invalid`
- `descriptor_alias_refused`, `descriptor_merge_refused`, `descriptor_explicit_tag_refused`
- `descriptor_duplicate_key`, `descriptor_too_deep`, `descriptor_too_many_events`
- `descriptor_sexagesimal_refused`, `descriptor_nonfinite`, `descriptor_invalid_unicode`

A non-mapping root remains `CatalogError`; model failures remain `ValidationError`.
These helper names do not extend the frozen package `__all__`. This deliberately
narrows third-party Python descriptor admission. Quoted descriptive strings are
preserved. Other implicit YAML 1.1 resolution (for example `1_000`) and Pydantic lax
schema coercion remain; the guard is not a new strict descriptor schema.

The opt-in [localhost project service](PROJECT_SERVICE.md) has its own versioned
submission contract, private immutable records and dedicated client, independent of
the public catalogue/index V1 APIs. All owner descriptor refusals map to constant
HTTP 422 `{"error":"invalid_descriptor"}`. Recipe intake admits strict
`pipeline.json` bytes only; YAML and `.n4a` replay integration stays open.
