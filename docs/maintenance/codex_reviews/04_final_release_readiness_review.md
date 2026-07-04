# Codex Gate 4 — final release-readiness (nirs4all-repository)

Per-repo final release-readiness is **consolidated into the ecosystem-level Gate 5**
(`nirs4all-ecosystem/docs/maintenance/codex_reviews/99_final_ecosystem_release_review.md`), which
reviews all hardened repos together. The per-repo Codex effort here was concentrated on **Gate 3**
(`codex exec review` of the diff — see `03_main_diff_review.md`); the comprehensive SHA-pinner
(0 floating tags remain across all 7 workflows, verified) removes the "missed-a-workflow" class of
defect that a separate per-repo Gate 4 would otherwise re-check.

**Readiness snapshot:** `repository` is the most mature in-scope repo — proper `vX.Y.Z` tags
(v0.1.0/0.1.1/0.1.2), an active (non-inert) version-guard, a full OS×Python test matrix, CodeQL +
dependency-review, least-privilege permissions, and now SHA-pinned actions + the community-health set.
**Documented (not blocking) roadmap:** enforce a coverage floor (`--cov-fail-under`) and add a CI
equality assert for the dual `VERSION` / `_version.py` source. Release path is via Trusted Publishing
on a `vX.Y.Z` tag at the exact release commit.
