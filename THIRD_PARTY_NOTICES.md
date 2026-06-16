# Third-Party Notices — nirs4all-repository

`nirs4all-repository` is distributed under `CeCILL-2.1 OR AGPL-3.0-or-later` (plus an optional
commercial license; see [`LICENSING.md`](LICENSING.md)). nirs4all-repository does **not** vendor the
components below — they are pulled from their official distributions — but their licenses are
acknowledged here as a courtesy and for compliance. Licenses are reported on a best-effort
basis; the authoritative text always ships with each upstream project.

The package itself depends only on a small set of pure-Python libraries; heavy scientific
dependencies (`numpy`, `nirs4all`, `dag-ml`) are optional and imported only on the
evaluation / bridging paths. Catalogue **content** (cards, metadata, the website) is
CC-BY-4.0.

| Component | License (SPDX) | Upstream |
|---|---|---|
| `pydantic` | MIT | https://github.com/pydantic/pydantic |
| `PyYAML` | MIT | https://github.com/yaml/pyyaml |
| `typer` | MIT | https://github.com/fastapi/typer |
| `nirs4all` & ecosystem (optional) | CeCILL-2.1 OR AGPL-3.0-or-later | https://github.com/GBeurier/nirs4all |
| `numpy` (optional, via nirs4all) | BSD-3-Clause | https://github.com/numpy/numpy |

For the exhaustive, version-pinned dependency tree and its licenses, inspect the
installed environment (e.g. `pip show <package>`); each pipeline's runtime dependencies
are determined by the framework that executes it.

License-family texts are bundled under [`LICENSES/`](LICENSES/): AGPL-3.0-or-later,
CeCILL-2.1, CC-BY-4.0, and the commercial license terms.
