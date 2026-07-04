# Codex Gate 3 — main diff review (nirs4all-repository)

**Reviewer:** Codex CLI 0.142.5 — `codex exec review --uncommitted`, 2026-07-04.
**Diff:** 4 community-health files (CODE_OF_CONDUCT, CITATION.cff, .editorconfig, .pre-commit-config),
SHA-pinned all third-party actions across 7 workflows (29 pins), CHANGELOG catch-up, docs/maintenance/.

## Verdict
> "The workflow/config additions appear syntactically valid." One accuracy finding, fixed.

## Findings & disposition

| # | sev | finding | disposition |
|---|---|---|---|
| P3 | minor | `CHANGELOG [0.1.2]` attributed **post-`v0.1.2`-tag** commits (portable recipe `91c1870`, archival-reject test `05f4a44`) to the already-released 0.1.2 — the 0.1.2 wheel cannot contain them. | **Fixed** — post-tag items moved to a new `## [Unreleased]` section; `[0.1.2]` now lists only genuine 0.1.2 content. |

## Note (surfaced by Codex during review)
Dependabot already has open PRs bumping these actions to newer majors (`actions/checkout` 4→6,
`actions/setup-python` 5→6, `dependency-review-action` 4→5, `configure-pages` 5→6, `deploy-pages` 4→5).
My SHA pins deliberately pin the **currently-used** major (v4/v5) — a behavior-preserving hardening
choice; the major upgrades are a separate, testable decision owned by Dependabot. Merge those PRs
after CI-green when ready.
