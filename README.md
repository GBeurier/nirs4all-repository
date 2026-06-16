# nirs4all-repository

> **Status: planned.** This repository is a shell for now — the design and the first
> pipelines are still to come. The description below is the intended role.

The public, versioned **repository of pre-configured, tested nirs4all pipelines** —
ready-to-run recipes (preprocessing → model → evaluation) that are validated against
reference datasets and can be loaded by name instead of being rebuilt by hand.

Part of the [nirs4all ecosystem](https://github.com/GBeurier/nirs4all-ecosystem).

## What it will provide

- **Curated, tested pipelines.** Each pipeline ships as a portable configuration plus the
  metadata needed to reproduce it, exercised in CI against curated datasets.
- **One source, many runtimes.** The same pipeline definitions are designed to be consumable from:
  - **nirs4all Studio** — pick a pre-configured pipeline from the UI.
  - **nirs4all** (Python) — the reference library.
  - **nirs4all-lite** bindings — R, MATLAB/Octave and the WASM/JS browser stack.
- **Stable, citable references.** Pipelines are versioned so results stay reproducible over time.

## Relationship to the rest of the ecosystem

- Pipelines are expressed against the public **nirs4all** pipeline surface and executed by its
  engine (or the portable lite/WASM stack); this repo does **not** re-implement NIRS, IO or ML logic.
- They are scored and compared in **nirs4all-benchmarks**; this repo is the *source of the recipes*,
  the benchmarks repo is *where they are run and ranked*.

## License

Pipeline **code / configurations** are dual-licensed open-source —
**`CeCILL-2.1 OR AGPL-3.0-or-later`** — with an optional **commercial license** (for any commercial
use, contact <nirs4all-admin@cirad.fr>). Bundled **content** (results, metadata) is **CC-BY-4.0**.
See [`LICENSING.md`](LICENSING.md) and [`LICENSES/`](LICENSES/).
