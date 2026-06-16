<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# Getting started

## Install

```bash
pip install nirs4all-repository
```

The package is pure-Python and lightweight; `numpy` / `nirs4all` / `dag-ml` are imported
only on the paths that need them (functional evaluation, bridging).

## Browse and resolve pipelines

```python
import nirs4all_repository as n4r

# Browse the catalogue (filters: framework, task, tag, kind, trust)
for entry in n4r.list(framework="nirs4all", task="regression"):
    print(entry["id"], "—", entry["summary"])

# Inspect one pipeline's full descriptor
n4r.card("snv_savgol_pls")

# Resolve by name: local checkout → wheel-bundled catalogue → remote (sha256-verified)
pipe = n4r.get("snv_savgol_pls")
```

## Run a recipe with nirs4all

```python
import nirs4all
pipe = n4r.get("snv_savgol_pls")
result = nirs4all.run(pipe.to_nirs4all(), "my_dataset/")
```

## The command line

The `n4a-repository` CLI is the maintenance interface:

```bash
n4a-repository list                       # browse
n4a-repository show snv_savgol_pls        # full descriptor
n4a-repository get snv_savgol_pls         # fetch to cache, print path
n4a-repository add my_pipe --recipe recipe.json --framework nirs4all
n4a-repository validate --all             # schema + structure + checksums + security
n4a-repository scan my_pipe               # security scan only
n4a-repository build                      # regenerate manifests + catalog/index.json
n4a-repository site --out site            # render the catalogue website
n4a-repository evaluate my_pipe           # run against the reference dataset
n4a-repository publish my_pipe            # check the publication gate
```

## Cross-language consumption

The catalogue is a static contract: any language fetches
`https://repository.nirs4all.org/data/index.json`, looks up a pipeline, downloads its
recipe `url`, and verifies the published `sha256`. See {doc}`SPECIFICATION` §9.
