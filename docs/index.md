<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# nirs4all-repository

The public, versioned **repository of pre-configured, tested NIRS pipelines** for the
nirs4all ecosystem. Store a `nirs4all` or `dag-ml` pipeline — with or without fitted
artifacts — with provenance, validate and secure it, and serve it **by name** to every
nirs4all library and tool, across languages, plus a catalogue website at
[repository.nirs4all.org](https://repository.nirs4all.org).

```{admonition} Status
:class: note
0.1.0 beta. The storage envelope and the cross-language `index.json` contract are frozen
at `schema_version: 1`.
```

## Quickstart

```bash
pip install nirs4all-repository
```

```python
import nirs4all_repository as n4r

n4r.list(framework="nirs4all")        # browse the catalogue
pipe = n4r.get("snv_savgol_pls")      # resolve by name (local → bundled → remote)
config = pipe.to_nirs4all()           # ready for nirs4all.run() / predict()
```

```{toctree}
:maxdepth: 2
:caption: Guide

getting_started
DESIGN
SPECIFICATION
ROADMAP
```

```{toctree}
:maxdepth: 2
:caption: Reference

api
```

## The ecosystem

`nirs4all-repository` is the **remote, name-addressable layer** the ecosystem otherwise
lacks: it stores the recipes that [`nirs4all`](https://github.com/GBeurier/nirs4all) runs
and [`nirs4all-benchmarks`](https://github.com/GBeurier/nirs4all-benchmarks) scores, and
serves them to nirs4all Studio and the lite/WASM bindings. It never re-implements NIRS,
IO, or ML logic.
