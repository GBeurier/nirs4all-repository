<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# nirs4all-repository — Roadmap

Versioned, milestone-driven. The 0.1.0 beta freezes the storage envelope and the
cross-language `index.json` contract (`schema_version: 1`); later milestones add
clients, fitted-artifact distribution at scale, and submission tooling without breaking
that contract.

## 0.1.0 — Beta (this milestone)

The complete, versioned, deployed beta.

- **Package** `nirs4all_repository` (pure-Python, src-layout): `PipelineDescriptor`
  model, catalogue store, local-first + remote `get`/`fetch`/`list`/`card`,
  `to_nirs4all()` / `to_dagml()` bridges, `Settings`.
- **Storage envelope** (`pipelines/<id>/` + RO-Crate manifest) and the canonical
  `catalog/index.json` registry, both frozen at `schema_version: 1`, with the
  min-readable/min-writable compatibility gate enforced from day one.
- **Pipelines with or without artifacts**: recipe pipelines end-to-end; the **fitted**
  path supported and tested for `storage: inline` artifacts (fixture-covered). Bulk
  `storage: release` hosting is 0.2.
- **Validation**: hermetic static validation (schema + structure + checksums + security)
  and the functional `evaluate` path against a reference dataset.
- **Security**: recipe class allow-list, pickle-opcode scan, tamper-evident checksums,
  trust tiers, publication gate.
- **CLI** `n4a-repository` (`list`/`show`/`get`/`add`/`validate`/`scan`/`build`/`site`/
  `evaluate`/`publish`).
- **Seed catalogue**: a small set of curated, validated *recipe* pipelines spanning
  `nirs4all` and `dag-ml`.
- **Website** `repository.nirs4all.org` (static, GitHub Pages, brand-faithful).
- **Docs** on ReadTheDocs (Sphinx) + this design set.
- **CI green**: lint + type + validate + freshness + tests + docs + Pages deploy +
  version-guard, all passing. Tag `v0.1.0`.
- **Ecosystem wiring**: `nirs4all-org` repository card → *Prototype* + link;
  `nirs4all-cockpit` gains the `pages` target + link map entry.

## 0.2.0 — Fitted artifacts at scale

- First-class **fitted** pipelines: artifact blobs published as GitHub Release assets,
  content-addressed, with the download/verify/cache path exercised end-to-end.
- **Sigstore** keyless build-provenance attestation on artifact releases (the
  `nirs4all-datasets` source-release pattern); SBOM for the wheel.
- A nightly/weekly **functional-evaluation CI matrix** re-running every pipeline
  against its pinned reference dataset and refreshing `evaluation.status`.

## 0.3.0 — Cross-language client packages

- Thin **R / MATLAB / JS-WASM** client packages over the frozen `index.json` contract
  (read + fetch + sha256-verify), mirroring the `nirs4all-formats` binding pattern.
- A small browser fetch helper shipped from the site for in-page "run this pipeline".
- `nirs4all-studio` integration: pick a repository pipeline by name from the UI.

## 0.4.0 — Submission & curation

- A **submission workflow**: PR template + bot that runs `validate --all --run` and the
  security scan, posts the report, and gates merge on the publication blockers.
- Community **trust promotion** (`experimental` → `community` → `official`) tied to
  passing evaluation + review.
- Catalogue **search/filtering** on the site backed by the index (client-side).

## 1.0.0 — Stable contract

- Freeze the public Python API and the `index.json`/descriptor `schema_version: 1`
  surface as a stable contract. (The min-readable/min-writable migration gate already
  ships in 0.1.0; 1.0.0 is where the *Python API* itself becomes a stability promise.)
- Full RTD reference, tutorials, and a contribution guide.
- Coverage and the functional-evaluation matrix as required gates.

---

© 2026 CIRAD — nirs4all ecosystem. Documentation is licensed CC-BY-4.0.
