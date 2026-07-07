<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# Changelog

All notable changes to **nirs4all-repository** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the public surface is stable in
shape but may still change before `1.0`.

## [Unreleased]

## [0.1.7] - 2026-07-08

### Changed
- Remove the retired `list_pipelines()` compatibility alias from the public Python
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
- Provider pipeline aliases exposed on the public API.

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
