# Release checklist — nirs4all-repository

Publishing is via **PyPI Trusted Publishing (OIDC)** (`publish.yml`, on GitHub Release / dispatch).
Pushing to `main` never publishes, but **does deploy GitHub Pages** to `repository.nirs4all.org`.

## Pre-release

- [ ] Green gate passes locally and on CI (see `quality_gates.md`).
- [ ] `CHANGELOG.md` has a dated entry for the target version.
- [ ] `VERSION` and `src/nirs4all_repository/_version.py` agree (single source of truth).
- [ ] Generated catalogue is current: `n4a-repository build && git diff --exit-code` clean.
- [ ] The test gate accepts nirs4all R1 (`0.13.0`) and the selected R2/R3
  (`1.0.0rc*`) versions through the `nirs4all` extra.
- [ ] `scripts/check_public_v1_surface.py` passes against the exact R1/R2/R3
  source heads pinned by `contracts/public-v1-surface.n4a.json`.
- [ ] `version-guard` green; the release **tag `vX.Y.Z` points at the exact release commit** (already-final manifest/changelog/catalogue).
- [ ] PyPI Trusted Publisher configured (project `nirs4all-repository`, owner `GBeurier`, `publish.yml`).

## Release

- [ ] Tag `vX.Y.Z` on the release commit and push the tag before merging the version
  bump to `main`; this is required by `version-guard`.
- [ ] Create the GitHub Release from that existing exact tag. Publishing it triggers
  `publish.yml`; manual workflow dispatch remains build-only.
- [ ] Confirm `publish.yml` green and the version is on PyPI.

## Post-release

- [ ] `pip install nirs4all-repository==X.Y.Z` in a clean venv; smoke `n4a-repository list`.
- [ ] Smoke `pip install "nirs4all-repository[nirs4all]==X.Y.Z"` against the exact
  nirs4all version selected by the product lock.
- [ ] Start the next `## [Unreleased]` CHANGELOG section.

## Notes

- Single-registry (PyPI) — no cross-registry partial-failure risk.
- SEO/site changes are published to `repository.nirs4all.org` on every push to `main` — review before merging.
