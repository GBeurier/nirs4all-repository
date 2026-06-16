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
