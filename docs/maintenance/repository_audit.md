# Repository audit — nirs4all-repository

> Generated from the automated pre-release audit (workflow wf_1fc87351-29f); the **Deepest hardening roadmap** section records the fullest realistic hardening even where the pragmatic pass does not implement it. Reviewed at Codex Gate 1.

- **Mode:** IN SCOPE — pragmatic hardening + push
- **Baseline HEAD:** `b82f5b6`
- **Role:** Pipeline repository: Python package + generated static catalogue site that stores, validates, secures, and serves pre-configured tested nirs4all/dag-ml pipeline recipes loadable by name, offline from a wheel-bundled catalogue.
- **Stack:** Python >=3.11 (3.11/3.12/3.13 tested). Build backend hatchling (dynamic version from _version.py). Runtime deps: pydantic>=2, pyyaml>=6, typer>=0.12. Optional extras: nirs4all>=0.10,<0.11, nirs4all-datasets>=0.3.2, dev (pytest/pytest-cov/ruff/mypy), docs (sphinx/myst/furo). Console script n4a-repository. Tooling: ruff (line-length 220), mypy (strict-ish), pytest. Docs: Sphinx+MyST+furo on Read the Docs. Packaging bundles pipelines/ + catalog/index.json into the wheel.

## Release-readiness verdict
nirs4all-repository is in strong, near-release-ready shape: clean tracked tree (108 files, no committed build artifacts or secrets), a full 3-OS x py3.11-3.13 test matrix (~67 tests), ruff+mypy gates, a catalogue-drift guard, CodeQL/dependency-review/dependabot, Sphinx+RTD docs, and PyPI publishing via OIDC Trusted Publishing — all workflows currently green. The main release-readiness gaps are hardening rather than blockers: actions are pinned to mutable tags instead of SHAs, coverage has no enforced floor, and a few community files (CODE_OF_CONDUCT, CITATION.cff, .editorconfig, pre-commit) are missing. Push-to-main is genuinely load-bearing here — it live-deploys the public GitHub Pages catalogue site and is policed by version-guard (VERSION must not lead the latest tag) and the catalogue-rebuild drift check, so version bumps and pipeline edits must follow a specific order. PyPI publishing itself is safely gated on GitHub Releases, not push. Recommended immediate wins: SHA-pin actions, add the missing standard files, and add a coverage floor + ruff format gate.

## Gate commands (detected)
| key | value |
|---|---|
| `install` | pip install -e ".[dev]" |
| `test` | pytest -m "not network and not evaluate" --cov=nirs4all_repository --cov-report=xml |
| `lint` | ruff check . |
| `typecheck` | mypy src/nirs4all_repository |
| `format` | — |
| `docs_build` | sphinx-build -b html docs docs/_build/html |
| `package_build` | python -m build |

## CI
- **Latest status:** All green. gh run list --limit 8 shows docs, CI, version-guard, Deploy Pages, CodeQL all [ok] on the latest main commits (b82f5b6). No failing runs.
- **Workflows:**
- ci.yml (lint ruff, type-check mypy, catalogue validate+build-drift, tests 3-OS x py3.11/3.12/3.13 matrix with coverage) — push/PR on main + rc/**
- codeql.yml (python, security-extended, weekly cron) — push/PR + schedule
- dependency-review.yml — PR only
- docs.yml (sphinx-build html, uploads artifact) — push/PR
- deploy-pages.yml (n4a-repository site → GitHub Pages, OIDC id-token) — push to main on pipelines/catalog/assets/site paths + dispatch
- publish.yml (build+twine check → PyPI Trusted Publishing OIDC, environment: pypi) — on release published + dispatch
- version-guard.yml (manifest-not-ahead-of-tag guardrail, shared ecosystem script) — push/PR
- **Gaps:**
- GitHub Actions pinned to mutable tags (@v4/@v5/@release/v1), not commit SHAs — supply-chain exposure despite dependabot github-actions weekly updates
- No coverage threshold enforced (--cov-report only; no --cov-fail-under); coverage.xml uploaded as artifact but not gated or sent to a coverage service
- ci.yml lint/type-check/docs lack a concurrency group (only deploy-pages has one) — redundant superseded runs on rapid pushes
- No ruff format check in CI (only ruff check .) — formatting drift not gated

## Standard files
- **Present:** readme, changelog, contributing, security, license, gitignore, pr_template, issue_template, dependabot
- **Missing:** code_of_conduct, citation, editorconfig, precommit

## Packaging
- **name:** `nirs4all-repository` — **version:** `0.1.2`
- **issues:**
- Version defined in two places kept in sync manually: src/nirs4all_repository/_version.py (__version__, hatch version source) and root VERSION file (read by version-guard + nirs4all-cockpit) — a unit test (tests/test_version.py) enforces byte-identity, but bumping one without the other fails CI
- hatch force-include copies catalog/index.json and pipelines/ into the wheel under _catalog/ — the generated index.json must be rebuilt and committed (CI `n4a-repository build && git diff --exit-code` enforces) or the wheel ships a stale catalogue
- License expression uses SPDX 'CeCILL-2.1 OR AGPL-3.0-or-later' with license-files glob — fine on modern hatchling/PEP639, but older pip/build toolchains may warn; verify twine check (already in publish.yml) stays green
- Optional deps pin nirs4all>=0.10,<0.11 and nirs4all-datasets>=0.3.2 — ecosystem-coupled ceilings that will need a bump in lockstep with the main lib release

## Tests
- **framework:** pytest (+pytest-cov), markers 'network' and 'evaluate' deselected in CI
- **estimate:** ~67 test functions across 10 files (test_api 8, test_build 6, test_canonical 7, test_cli 6, test_markdown 7, test_recipes 12, test_schema 13, test_security 7, test_version 1, plus conftest factory)
- **coverage:** pytest-cov configured ([tool.coverage.run] source=nirs4all_repository, omit tests); measured on ubuntu py3.11 and uploaded as artifact; NO fail-under threshold, no Codecov/coveralls integration

## Docs
- **system:** Sphinx + MyST-Parser (furo theme, sphinx-design, copybutton, opengraph, autodoc/napoleon) — docs/conf.py; pages in docs/*.md (index, getting_started, api, DESIGN, SPECIFICATION, ROADMAP). Read the Docs configured via .readthedocs.yaml (ubuntu-24.04, py3.12, docs/requirements.txt + pip install .)
- **status:** Buildable and building green: docs.yml CI job runs sphinx-build -b html and passes; RTD config valid; autodoc_mock_imports covers heavy optional deps (nirs4all, dag_ml, numpy). A stale docs/_build/ tree exists on disk but is gitignored (not tracked).

## Risks
| severity | area | detail |
|---|---|---|
| high | ci/push | .github/workflows/deploy-pages.yml deploys the live GitHub Pages catalogue site (repository.nirs4all.org) on every push to main touching pipelines/**, catalog/**, assets/**, or site/** — merging to main publishes the public site with no manual gate. |
| medium | ci/push | .github/workflows/ci.yml `catalogue` job runs `n4a-repository build && git diff --exit-code` — any edit to pipelines/ or descriptors without regenerating and committing catalog/index.json fails CI on push; the generated index must always be committed in the same change. |
| medium | supply-chain | All workflow actions use mutable tag refs (actions/checkout@v4, setup-python@v5, pypa/gh-action-pypi-publish@release/v1, github/codeql-action@v3, etc.) rather than pinned commit SHAs — a compromised tag would run in the OIDC-privileged publish/pages jobs. |
| low | version-sync | Version is duplicated across src/nirs4all_repository/_version.py and root VERSION; version-guard.yml (shared ecosystem script) fails any push where VERSION is ahead of the latest git tag — a bump merged to main before its tag exists blocks CI. |
| low | coverage | No --cov-fail-under threshold and no external coverage service; coverage can silently regress since it is only uploaded as an artifact. |

## Security
- **info** — Light secret scan over src/ (private-key headers, aws_secret, api_key/token assignments with 16+ char literals) found NO matches — no plausible leaked credentials in tracked source.
- **info** — PyPI publishing uses Trusted Publishing (OIDC, environment: pypi, id-token: write scoped to the publish job) — no long-lived API token stored. Good posture.
- **info** — SECURITY.md present (3.8K); CodeQL security-extended + dependency-review + dependabot (pip + github-actions weekly) all configured. All top-level workflow permissions default to contents: read with least-privilege escalation only where needed (pages/id-token in deploy-pages, security-events in codeql, id-token in publish).
- **low** — The package's own domain (nirs4all-repository) validates and executes recipe descriptors; src/nirs4all_repository/security.py + markdown_safe.py + test_security.py indicate a deliberate untrusted-recipe threat model — worth a security-review focus before opening the recipe repo to external contributions.

## Quick wins (pragmatic scope — safe to apply now)
- Pin all GitHub Actions to full commit SHAs (with a version comment) across the 7 workflows; dependabot github-actions is already configured to bump them
- Add CITATION.cff — repo advertises reproducibility/provenance and DOI-citable ecosystem; low-risk metadata add
- Add CODE_OF_CONDUCT.md (Contributor Covenant) — only standard community file missing
- Add .editorconfig to match ruff line-length/py311 conventions
- Add .pre-commit-config.yaml mirroring CI (ruff check, ruff format, mypy) so contributors catch failures locally
- Add a `concurrency` group (cancel-in-progress) to ci.yml, docs.yml, codeql.yml to kill superseded runs — deploy-pages already models this
- Add `ruff format --check .` as a CI format gate (ruff already installed) to lock formatting
- Add `--cov-fail-under=<N>` to the pytest gate to freeze the current coverage floor

## Deepest hardening roadmap (fullest realistic hardening)
- Establish a coverage floor (--cov-fail-under) and wire Codecov/Coveralls with a PR status; ratchet toward 90%+ on the pure-Python core (schema/validate/security/canonical/manifest)
- SHA-pin every action and add a permissions review; consider zizmor or actionlint in CI to lint workflows for privilege/injection issues
- Add build provenance/attestation: SLSA/`actions/attest-build-provenance` on the publish.yml artifacts, and Sigstore signing of the sdist/wheel
- Publish the RTD site (currently only CI-built + RTD-configured) and add a docs link-check + `-W` (warnings-as-errors) sphinx build to prevent doc rot
- Formalize the release runbook: since version-guard forbids VERSION ahead of tag, document/automate the tag-then-bump (or simultaneous) order; optionally adopt release-please or a make-release script that tags v{VERSION} atomically to remove the manual two-file (_version.py + VERSION) sync footgun
- Add a smoke workflow that installs the built wheel in a clean env and runs `n4a-repository get <recipe>` fully offline to prove the force-included catalogue ships correctly
- Add an optional integration lane exercising the `[nirs4all]`/`[datasets]` extras (the deselected `evaluate` marker) on a schedule to catch ecosystem-version drift against nirs4all 0.10.x
- Harden the untrusted-recipe threat model: fuzz/property tests on schema.py + markdown_safe.py + security.py, and a documented recipe-signing/checksum trust chain (RO-Crate metadata already present) before accepting external pipeline contributions
- Add SBOM generation (CycloneDX) to the publish pipeline and surface it as a release asset
- Add editorconfig/pre-commit/CODE_OF_CONDUCT/CITATION and a CONTRIBUTING section describing the `n4a-repository build` catalogue-regeneration requirement so external PRs don't fail the drift gate

## Push-safety notes
- deploy-pages.yml: push to main touching pipelines/**, catalog/**, assets/**, or src/nirs4all_repository/site/** immediately rebuilds and deploys the live public GitHub Pages catalogue site (id-token: write, pages: write) — no manual approval; a bad merge ships to the public site.
- version-guard.yml: runs on every push to main/rc — FAILS if root VERSION (currently 0.1.2) is ahead of the latest git tag. A version-bump commit merged to main before the matching v{VERSION} tag exists will red the branch. Release must tag at or before the bump lands.
- ci.yml `catalogue` job: `n4a-repository build && git diff --exit-code` — pushing pipeline/descriptor edits without committing the regenerated catalog/index.json breaks main CI.
- tests/test_version.py enforces src/nirs4all_repository/_version.py __version__ == VERSION byte-for-byte — bumping one file without the other fails the push.
- publish.yml is gated on GitHub Release published (not push), using OIDC Trusted Publishing to the `pypi` environment — pushing to main does NOT publish to PyPI, so that path is safe; the risk is only if a release is cut from an unintended commit.
- Cross-repo coupling: VERSION is consumed by nirs4all-cockpit and version-guard is a shared ecosystem guardrail; optional deps pin nirs4all>=0.10,<0.11 — an ecosystem lib release can force a coordinated bump here.
