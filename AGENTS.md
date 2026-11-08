# Repository contributor instructions

## Recipes and requirements

Repository owns complete recipes, presets, provenance and versioned execution requirements; runtime/compiler owners lower and execute them or explicitly refuse. Preserve parameters, branches, search, targets, scalar types, aliases and mapping order. Storage/static validation is not runtime qualification; keep unknown versions/profiles/operations/artifact versions and dependency coverage explicitly unknown.

Keep recipe security scanning separate from contextual dependency observations. Static structure/security/checksum failures must prevent opt-in strict framework imports. Preserve curated module-root admission, uncertain executable-reference refusals and unqualified native-alias refusals; the developer allowlist environment override never widens CI/publication. Pickle scanning is heuristic, not a sandbox; fitted artifacts remain opt-in with warnings.

Retain official/community/experimental trust tiers. Publication requires open license, author/provenance, static validation and security scan; official/community also require functional `n4a-repository evaluate` validation. Experimental content stays labelled unvalidated. Verify HTTPS bytes by SHA-256 before use and never replay credentials across redirects. Reference data stays at its owning origin.

## Local project content and deferred consumers

The optional [local project service](docs/PROJECT_SERVICE.md#startup-and-credentials) is independent of offline/public catalogue APIs and has no Cluster dependency. Keep POSIX/localhost-only scope, private project stores, immutable credential snapshots, pre-body exact rights and no public fallback, execution, publication or fitted-artifact admission. Preserve exact admitted recipe bytes and explicit format/claim refusals. Uvicorn 0.49.0 is the named evidence limit, not a guarantee for every host/version; service acceptance and release are not established here.

Preserve fixed quiet transport/error diagnostics and bounded descriptor parsing. Keep mandatory POSIX service qualification distinct from optional dependency skips; required mode must fail when its leaf is absent. Throwaway-token negative-control logs remain private and must never use production credentials. Local materialization errors may retain local paths; do not claim a universal client diagnostic guarantee.

Studio preset authoring inversion, snapshot sync, frontend pins and generated rendering remain deferred to the joint maintainer batch. Preserve full-tree recipe parity and unevaluated status; importing a preset does not establish results or model dependencies. `docs/maintenance/repository_preset_batch.md` is historical evidence, not operative instruction authority.

## Commands and licensing

From the package checkout, use the [contributor setup and gate](CONTRIBUTING.md#the-green-gate-run-before-every-commit); maintain generated manifests/RO-Crate/index with their full conditions:

```bash
ruff check .
mypy src/nirs4all_repository
n4a-repository validate --all
n4a-repository build && git diff --exit-code
pytest -m "not network and not evaluate"
```

Keep Google docstrings, public types, configured line length and source SPDX headers. Optional integration, functional evaluation, service-required-mode and release checks retain their separate prerequisites; no docs-only run is called a product green gate.

Follow [SECURITY](SECURITY.md) for private reporting and [LICENSING](LICENSING.md): code/configurations use `CeCILL-2.1 OR AGPL-3.0-or-later` with the published commercial option; content uses CC-BY-4.0, subject to upstream terms.

## Working rules

Read applicable local and deeper instructions before editing. Preserve dirty/concurrent work and make only authorized changes. When a workspace policy exists at `../AGENTS.md`, read it within the current user scope; this local policy also works in a standalone checkout. An existing `CLAUDE.md` is a compatibility entrypoint, not a second policy dependency.

Use CodeGraph FIRST for implementation navigation only when this checkout has its own `.codegraph/`; use its exact projectPath or run the CLI here. Never auto-index or substitute an ancestor index. Unindexed code, docs and configs use ordinary source navigation; source, tests and build tools remain final authority.

Keep secrets, private data, generated workspaces, caches and build outputs out of Git. Respect owner licenses and fixture restrictions, record actual commands/exits/skips, and preserve scoped authorization: command examples do not grant installation, science, publishing, hosting or frontend work.

All application and project content must be in English, including UI text, subtitles, tooltips, errors, documentation, comments and docstrings, test and fixture prose, reports, pull requests, commits, and generated content. Conversation with the maintainer may be in French. Preserve proper names, identifiers, filenames, source quotations, and historical or provenance records where translation would change their meaning or provenance.
