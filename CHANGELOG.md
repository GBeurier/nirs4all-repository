<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# Changelog

All notable changes to **nirs4all-repository** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the public surface is stable in
shape but may still change before `1.0`.

## [Unreleased]

## [0.1.13] - 2026-11-03

### Added
- Studio preset catalogue: the ten default Studio presets (simple, fast result, simple trees,
  complex PLS, complex trees, nonlinear exploration, ultra PLS, ultra trees, deep nonlinear
  exploration, ultra slow) as 20 `studio_*` recipes with regression and classification variants.
  Recipes are copied unchanged from Studio's authored YAML, marked `draft` and unevaluated.
  `catalog/studio-presets.json` records the Studio source commit and the SHA-256 of every
  authored file; it and the pre-rendered preset cards ship in the wheel.
- `scripts/sync_studio_presets.py` imports the presets from a Studio checkout, and
  `npm run build:cards` / `npm run check:cards` render and verify the preset cards with the
  shared `PipelinePresetCard` of the pinned `nirs4all-ui` 0.2.1 artifact, refusing a snapshot that
  differs from the catalogue consumed by Web. CI and the Pages deployment run `check:cards`.
  `npm run test:site` is a browser smoke test of the built site.
- Accept `tabpfn` among the allow-listed recipe module roots and `_cartesian_` as a nirs4all step
  keyword, as the Studio presets use both.

### Changed
- The catalogue site opens on the Studio presets with a task filter, a responsive layout and
  accessible filter chips; the previous recipes are listed under "Additional repository recipes".
- The Repository surface contract keeps the five original train recipes required and reports the
  other catalogue recipes as `additional_recipe_ids`, so new recipes do not rewrite the frozen
  R1/R2/R3 compatibility evidence. All 25 nirs4all recipes load through the public
  `nirs4all.PipelineConfigs` on nirs4all 0.13.0 and 1.4.14.
- Pin catalogue line endings to LF in `.gitattributes` so bundle checksums verify on every platform.
- Remove maintenance plans already archived in the consolidated ecosystem backlog.

### Fixed
- The `studio_fast_result_regression`, `studio_complex_pls_regression` and
  `studio_ultra_slow_regression` recipes pass the native AOM-PLS keywords (`max_components`,
  `center_x`, `scale_x`), and the ultra slow search tunes `max_components` 1..27. The previous
  `n_components`/`center`/`scale` (and `n_orth`/`operator_index`) were dropped by nirs4all 1.4, so
  the 12-component model ran with `max_components=3` and the search tuned nothing. Synced from
  Studio through `nirs4all-ui` 0.2.1.

### Known issues
The recipes declare valid constructor keywords, but on nirs4all 1.4.14 some steps fail at run time
because of nirs4all/DAG-ML defects, to be fixed there:
- `AOMPLSClassifier` (fast result, complex PLS, ultra PLS and ultra slow classification): nirs4all
  injects its pipeline folds into the classifier's integer `cv`.
- `PLSDA` / `OPLSDA` (simple, complex and ultra PLS, ultra slow classification): DAG-ML rejects
  their class scores as probabilities.
- XGBoost steps (complex trees, nonlinear, deep nonlinear and ultra trees recipes): DAG-ML fails to
  parse the generated pipeline JSON.

### CI
- Update the CodeQL actions to 4.38.3 and `pypa/gh-action-pypi-publish` to 1.14.3.

## [0.1.12] - 2026-09-04

### Changed
- Repin the Repository public-surface contract to the rollback-corrected Python
  R2/R3 candidate heads, with R3 retained as the direct child of R2.
- Supersede the `0.1.11` compatibility receipt without removing that historical
  release. No public API, provider entry point, or bundled recipe changes.

## [0.1.11] - 2026-09-03

### Fixed
- Extend the optional nirs4all integration window through R1 (`0.13.0`) and the
  R2/R3 `1.0.0rc*` train while retaining compatibility with 0.10–0.12.
- Use the public `nirs4all.PipelineConfigs` export for strict recipe validation instead
  of depending on nirs4all's internal module layout.
- Keep the public `fetch()` function callable after the same-named internal module has
  been imported, including through provider `get_bundle()` calls.
- Require exact agreement between the release tag, `VERSION`, wheel, and sdist before
  upload, and keep manual publication dispatches build-only.

### Tests
- Freeze the Repository public/provider surface and prove all five bundled nirs4all
  recipes load through public `PipelineConfigs` on the exact R1/R2/R3 source heads.

## [0.1.10] - 2026-07-08

### Fixed
- Regenerate the committed catalogue index for the provider-entry-point
  documentation release.

## [0.1.9] - 2026-07-08

### Changed
- Clarify that `get_pipeline_list()`, `get_pipeline()`, and `get_bundle()` are the
  canonical provider-facing API entry points.

## [0.1.8] - 2026-07-08

### Changed
- Reword provider-facing `get_pipeline_list()`, `get_pipeline()`, and
  `get_bundle()` as stable entry points in the provider contract. No
  behavior changed.

## [0.1.7] - 2026-07-08

### Changed
- Remove the retired `list_pipelines()` compatibility method from the public Python
  API and docs. `get_pipeline_list()` is the single provider-facing list method.

## [0.1.6] - 2026-07-06

### Added
- Add a release-asset hygiene check for latest or tagged GitHub Releases.

### Fixed
- Scan fitted pickle artifacts during validation and publication security checks.

### CI
- Attach the built wheel and sdist to GitHub Releases and verify both assets before the
  release workflow finishes.

## [0.1.5] - 2026-07-06

### Fixed
- Regenerate the committed catalogue index after the 0.1.4 package version bump.

## [0.1.4] - 2026-07-06

Changes on `main` after the `v0.1.3` tag.

### Added
- Core portable repository recipe.

### CI
- Preserve the custom GitHub Pages domain and add a dry-run dispatch path for repository publishing.

### Tests
- Reject archival paper step records in recipes.

## [0.1.2] - 2026-07-03

Released together with 0.1.1 (same tree). Additive changes on top of the 0.1.0 beta; the
storage envelope and the cross-language `index.json` contract (`schema_version: 1`) are unchanged.

### Added
- Provider-facing pipeline entry points exposed on the public API.

### Fixed
- Platform-independent `is_safe_relpath` (Windows path-safety).
- Canonical SEO metadata and the canonical nirs4all.org teal palette on the site.

### CI
- Emit a coverage artifact (`coverage.xml`) for the nirs4all cockpit; cover `rc/**` branches.

## [0.1.0] - 2026-06-17

The first beta. Freezes the storage envelope and the cross-language `index.json`
contract at `schema_version: 1`.

### Added
- `nirs4all_repository` package (pure-Python, src-layout): `get` / `fetch` / `list` /
  `card`, the `Pipeline` handle with `to_nirs4all()` / `to_dagml()` bridges, and
  `Settings`. Resolution is local checkout → wheel-bundled catalogue → remote
  (SHA-256-verified, content-addressed cache).
- `PipelineDescriptor` schema (Pydantic v2) with a dag-ml-style schema-version
  compatibility gate (`SCHEMA_VERSION` / `MIN_READABLE` / `MIN_WRITABLE`).
- Storage envelope `pipelines/<id>/` (descriptor + recipe + card + generated
  `manifest.json` + RO-Crate metadata) and the canonical-JSON `catalog/index.json`
  registry. Supports **recipe** and **fitted** (`storage: inline`) pipelines.
- Validation: hermetic static validation (schema, structure, checksums, security) and
  functional `evaluate` against a reference dataset.
- Security: curated recipe class allow-list, pickle-opcode scan, SHA-256 tamper-evidence,
  trust tiers, and a publication gate requiring functional validation for
  official/community pipelines.
- `n4a-repository` CLI (`list` / `show` / `get` / `add` / `validate` / `scan` / `build` /
  `site` / `evaluate` / `publish`).
- Static catalogue-site renderer for `repository.nirs4all.org` (brand-faithful, safe
  Markdown, GitHub Pages deploy).
- Seed catalogue: four `nirs4all` recipes and one `dag-ml` recipe.
- ReadTheDocs (Sphinx + furo) documentation and the DESIGN / SPECIFICATION / ROADMAP set.
