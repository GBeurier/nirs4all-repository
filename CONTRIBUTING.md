<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# Contributing to nirs4all-repository

Thanks for helping grow the catalogue. This repo stores **pipelines**, not NIRS/ML
logic — that lives in `nirs4all` and `dag-ml`. Contributions are either a new pipeline or
an improvement to the tooling.

## Setup

```bash
uv venv --python 3.11 && source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Add a pipeline

```bash
n4a-repository add my_pipe --recipe path/to/recipe.json --framework nirs4all
# edit pipelines/my_pipe/descriptor.yaml and card.md
n4a-repository build                 # regenerate manifests + catalog/index.json
n4a-repository validate my_pipe      # schema + structure + checksums + security
```

A pipeline directory holds `descriptor.yaml`, the recipe (`pipeline.json`), and
`card.md`; the `manifest.json`, `ro-crate-metadata.json`, and `catalog/index.json` are
**generated** — always commit them current (`n4a-repository build`), CI checks they have
no drift.

## The green gate (run before every commit)

```bash
ruff check .
mypy src/nirs4all_repository
n4a-repository validate --all
n4a-repository build && git diff --exit-code
pytest -m "not network and not evaluate"
```

## Conventions

- Python: Google-style docstrings, type hints on the public surface, ruff line-length
  220, `# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later` on every `.py`.
- Recipes reference only allow-listed module roots (see `SECURITY.md`); the scan rejects
  anything else.
- An `official`/`community` pipeline must pass functional validation
  (`n4a-repository evaluate`) before it can be `published`.

By contributing you agree your contribution is licensed under
`CeCILL-2.1 OR AGPL-3.0-or-later` (code) / CC-BY-4.0 (content).

## Cross-repository version constraints

Versions are `X.Y.Z`. A patch (`Z`) carries fixes and purely additive,
backward-compatible features: existing outputs, wire formats, schemas and ABI
symbols are unchanged. A minor (`Y`) carries any compatibility break: a changed
or removed API signature, an ABI break or ABI version change, a wire, byte,
schema or fixture change, renamed ids or changed numerical results of existing
operations. The package that bumps classifies its change.

Dependencies on packages from other nirs4all repositories accept every patch of
one tested series, `>=X.Y[.Z],<X.(Y+1)`. A patch floor is allowed when a fix or
feature from that patch is required; moving to a new series is an explicit,
tested decision of the consumer. For 1.x packages the upper bound is the next
minor, never `<2` (npm `~1.4.1`, Cargo `">=1.4.1, <1.5"`, Python
`>=1.4.1,<1.5`). A patch release of this package keeps its
catalog/recipe contracts under `contracts/` unchanged.

Current declarations: `nirs4all-datasets>=0.3,<0.4`, `nirs4all-access>=0.1,<0.2`
and `nirs4all>=0.10,<2.0.0.dev0` (the historical supported line, whose `.dev0`
bound keeps the 1.0 release candidates admitted and 2.0 pre-releases excluded;
see `tests/test_train_compatibility.py`); that SDK range predates this rule and
is aligned at the next release. Exact versions live in lockfiles and the release
order; the `nirs4all-ui` tarball in `package.json` is a vendored artifact. The
full policy is `docs/contracts/release/VERSION_CONSTRAINTS.md`
in `nirs4all-ecosystem`.
