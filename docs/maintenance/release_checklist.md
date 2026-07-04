# Release checklist — nirs4all-repository

Publishing is via **PyPI Trusted Publishing (OIDC)** (`publish.yml`, on GitHub Release / dispatch).
Pushing to `main` never publishes, but **does deploy GitHub Pages** to `repository.nirs4all.org`.

## Pre-release

- [ ] Green gate passes locally and on CI (see `quality_gates.md`).
- [ ] `CHANGELOG.md` has a dated entry for the target version.
- [ ] `VERSION` and `src/nirs4all_repository/_version.py` agree (single source of truth).
- [ ] Generated catalogue is current: `n4a-repository build && git diff --exit-code` clean.
- [ ] `version-guard` green; the release **tag `vX.Y.Z` points at the exact release commit** (already-final manifest/changelog/catalogue).
- [ ] PyPI Trusted Publisher configured (project `nirs4all-repository`, owner `GBeurier`, `publish.yml`).

## Release

- [ ] Tag `vX.Y.Z` on the release commit; publish the GitHub Release (triggers `publish.yml`).
- [ ] Confirm `publish.yml` green and the version is on PyPI.

## Post-release

- [ ] `pip install nirs4all-repository==X.Y.Z` in a clean venv; smoke `n4a-repository list`.
- [ ] Start the next `## [Unreleased]` CHANGELOG section.

## Notes

- Single-registry (PyPI) — no cross-registry partial-failure risk.
- SEO/site changes are published to `repository.nirs4all.org` on every push to `main` — review before merging.
