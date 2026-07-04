# Quality gates — nirs4all-repository

## Local green gate (run before every push)

```bash
pip install -e ".[dev]"                                   # install
ruff check .                                              # lint (line-length 220, py311)
mypy src/nirs4all_repository                              # types
n4a-repository validate --all                             # every descriptor: schema + structure + checksums + security
n4a-repository build && git diff --exit-code              # generated catalogue must be current (committed)
pytest -m "not network and not evaluate" --cov=nirs4all_repository --cov-report=xml
```

Optional local hooks mirroring the gate (`pre-commit` fetched on demand via `uvx`):

```bash
uvx pre-commit install
uvx pre-commit run --all-files
```

## CI gates (`.github/workflows/`)

| workflow | trigger | gate |
|---|---|---|
| `ci.yml` | push/PR `main`, `rc/**` | lint (ruff) · type-check (mypy) · catalogue (`validate --all` + `build` diff) · tests **matrix ubuntu/windows/macOS × 3.11/3.12/3.13** with coverage |
| `codeql.yml` | push/PR + schedule | CodeQL SAST |
| `dependency-review.yml` | PR | dependency review |
| `docs.yml` | push/PR | docs build |
| `deploy-pages.yml` | push `main` / dispatch | GitHub Pages deploy → `repository.nirs4all.org` |
| `publish.yml` | release / dispatch | PyPI Trusted Publishing (OIDC) — **not** on push |
| `version-guard.yml` | push/PR | manifest not ahead of latest `v*` tag |

All workflows declare least-privilege `permissions`; **all third-party actions are now SHA-pinned**
(29 pins across 7 workflows), Dependabot-tracked. Version scheme is the proper `vX.Y.Z` (v0.1.0/0.1.1/0.1.2
tagged) so `version-guard` is active (not inert).

## Known gaps (deepest-hardening roadmap)

- **Coverage measured but not gated.** CI emits `coverage.xml`; add `--cov-fail-under=<floor>` once agreed, then ratchet.
- **Dual version source** (`VERSION` + `src/nirs4all_repository/_version.py`) — add a CI equality assertion so a bump cannot half-land.
- Pages deploys on push to a public domain; keep site content changes deliberate.
