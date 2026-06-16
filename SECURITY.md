<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in `nirs4all-repository`, please **do not open
a public GitHub issue**.

Instead, report it privately via one of the following channels:

- **GitHub Security Advisories**: use the "Report a vulnerability" button on the
  [Security tab](https://github.com/GBeurier/nirs4all-repository/security/advisories/new)
  of this repository.
- **Email**: contact the maintainer at
  [gregory.beurier@cirad.fr](mailto:gregory.beurier@cirad.fr) with the subject line
  `[SECURITY] nirs4all-repository vulnerability`.

Please include a description of the vulnerability and its impact, steps to reproduce,
and any suggested mitigations. We aim to acknowledge reports within **5 business days**
and to provide a fix or mitigation within **30 days** for confirmed issues.

## Threat model — what this repository defends against

`nirs4all-repository` stores and serves **pipelines**: small text *recipes* and,
optionally, *fitted* artifacts. Both are code-execution vectors, and the catalogue is
public and accepts contributions. The defences, in order of strength:

1. **Recipe class allow-list.** A recipe references Python classes by dotted path
   (`"class": "sklearn..."`). The security scan rejects any class whose top-level module
   is outside a **curated** allow-list (`sklearn`, `scipy`, `numpy`, `nirs4all`,
   `dag_ml`, `aom_nirs`, …). This blocks config-borne injection such as `os.system` or
   `builtins.eval`. The `NIRS4ALL_REPOSITORY_ALLOWLIST` environment variable is a
   **local developer convenience only** — CI and the publication gate always use the
   built-in curated list and ignore it, so it can never widen what is published.

2. **Tamper-evidence (content addressing).** Every bundle file carries a SHA-256 in the
   manifest and the RO-Crate metadata. `verify()` recomputes the data-file digests and
   refuses on any mismatch. All downloads are HTTPS-only, verified against the published
   SHA-256 **before use**, and credentials are never replayed across a redirect.

3. **Pickle-opcode scan (heuristic, not a sandbox).** Fitted artifacts are
   pickle/joblib blobs, which can execute arbitrary code on load. Before a fitted
   pipeline is published, its artifact bytes are scanned with `pickletools` for
   `GLOBAL`/`STACK_GLOBAL` opcodes importing modules outside the allow-list or known
   dangerous callables (`os`, `posix`, `subprocess`, `builtins.eval`/`exec`, `socket`,
   …). **This is a defence-in-depth heuristic, not a security boundary.** Unpickling an
   untrusted artifact can still be unsafe; loading fitted artifacts is therefore opt-in
   (`get(..., with_artifacts=True)`) and the API/CLI warn before any pickle is opened.

4. **Trust tiers + publication gate.** Pipelines carry a trust tier (`official` /
   `community` / `experimental`). A pipeline may be marked `published` only with an open
   license, an author, provenance, passing static validation, and a passing security
   scan; `official`/`community` additionally require functional validation
   (`evaluation.status == validated`). `experimental` pipelines are labelled as
   unvalidated everywhere they appear.

### Out of scope

- The internal byte structure of a nirs4all `.n4a` bundle is validated by `nirs4all`'s
  own `BundleLoader`, not re-implemented here.
- Vulnerabilities in optional dependencies (`nirs4all`, `dag-ml`, scikit-learn, …)
  should be reported to those projects.
- The catalogue website is a static, generated site; authored content is sanitised at
  render time (HTML-escaped; `card.md` rendered with a safe Markdown subset).
