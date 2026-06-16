<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# Changelog

All notable changes to **nirs4all-repository** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the public surface is stable in
shape but may still change before `1.0`.

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
