<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# Local project recipe service

The optional `project-service` extra adds an authenticated, POSIX, localhost-only
ASGI backend. Offline catalogue imports, `list`, `card`, `get`, exports and their
public V1 surface remain independent of `nirs4all-access` and Uvicorn. Project
records have no public catalogue fallback, publication, execution or fitted-artifact
admission. This implementation has not received independent service acceptance or a
release. Provider, Arena, Studio, UI and non-Python integrations are deferred.

## Startup and credentials

The extra declares independent `nirs4all-access>=0.1,<0.2` and
`uvicorn>=0.30,<1`. It has no Cluster dependency. The access leaf must be available
before this extra can resolve publicly. Qualification used an existing wheel-derived
access 0.1.0 environment and Uvicorn **0.49.0**; no other Uvicorn version is qualified
by these tests.

```bash
n4a-repository-project serve --store /private/project-records \
  --credentials /private/project-credentials.json --port 8123
```

`python -m nirs4all_repository.project_service serve` provides the same entry point.
The credential file is the leaf's private, hash-only credential store, not a token
file. Startup freezes an immutable verifier snapshot and requires at least one
unrevoked, unexpired credential granting `repository.read` or `repository.add`.
Revocation or rights changes take effect on restart. An admin-only credential does
not satisfy startup. Tokens are never accepted in command-line arguments.

`--host` accepts only `127.0.0.1` (default), `::1`, or `localhost`. There are no TLS,
proxy, HTTP parser, WebSocket or logging flags. Uvicorn uses fixed
`log_level="warning"`, `access_log=False`, `ws="none"`, `http="h11"`,
`proxy_headers=False`, `server_header=False`, `loop="asyncio"`, and
`limit_concurrency=32`. At most four ingests run concurrently. There is no separate
header timeout: idle local sockets with partial headers can exhaust the concurrency
limit and deny service to health checks and authenticated requests (503). The review
reproduced this with 32 unauthenticated sockets sending `GET /v1/rec`; it persisted
past six seconds and recovered when those sockets closed. The concurrency limit does
not prevent this local denial of service. This remains a known localhost limitation.
WebSocket upgrades cannot establish a WebSocket. Direct ASGI WebSocket scopes close
with code 1008. Upgrade warnings contain fixed transport text only.

The store must be outside any catalogue checkout and private (0700). Its operator
and filesystem are trusted; remote credentials confer no filesystem administration.
New files are private, and record reads open every directory and file without
following symlinks. Project directories are created lazily. No other project is
scanned. Free space must remain at least **2147483648 bytes** before a new record;
`--disk-floor` can raise that floor. An identical existing record can still be read
or replayed at low space. POSIX rename and fsync semantics are required; Windows is
unsupported for this service.

## HTTP contract

| Method and path | Right | Response |
| --- | --- | --- |
| `GET /healthz` without a query | None | 200 `{"status":"ok"}` |
| `POST /v1/records` | `repository.add` | 201 `{"status":"created","record":{…}}`, or 200 with `status: already_present` and the original record |
| `GET /v1/records` | `repository.read` | 200 `{"records":[…]}` |
| `GET /v1/records/{record_id}` | `repository.read` | 200 record with base64 source files |

There are no selectors, filters, pagination, update, delete or file routes. Clients
filter locally. All protected routes, including unknown methods and paths, require
exactly one `Authorization: Bearer …` header and authenticate before reading a body.
An unknown route verifies the service grant without demanding a route right, then
returns 404. `/healthz` with any query also goes through authentication and is an
unknown route. On recognized routes, every query and every header name containing
`project` is refused as 400 `invalid_request`. Upgrade headers are also refused.
Project ownership comes exclusively from the verifier principal, never from input.

401 is exactly `{"error":"invalid_credential"}` with `WWW-Authenticate: Bearer`.
403 is `{"error":"service_not_granted"}` or
`{"error":"missing_rights","missing_rights":["repository.add"]}` (sorted required
rights). Leaf diagnostic text and principal IDs are never included in errors.
Unknown and foreign records return identical 404 `{"error":"not_found"}` bodies.
All responses are JSON, `Cache-Control: no-store`, and close the connection, including
refusals with unread bodies and `Expect: 100-continue`.

POST requires `application/json` (optional media-type parameters are accepted), and
absent or identity content encoding. Other media types/encodings return 415
`unsupported_media_type`. Duplicate content lengths or length plus transfer encoding
return 400. Declared and actual body bytes are capped at 1 MiB; each decoded file is
capped at 512 KiB. These give 413 `body_too_large` or `file_too_large`. The total body
deadline is 30 seconds (408 `body_timeout`). A disconnect gives 400 `invalid_request`.
Unhandled owner failures return only 500 `{"error":"internal_error"}`. The service
never logs or formats request scope, paths, headers, query strings or exception text.

## Submission, refusal order and source fidelity

The wire shape is specified in
[`project-submission.v1.schema.json`](../contracts/project-submission.v1.schema.json):

```json
{"schema":"nirs4all-repository/project-submission/v1","files":[
  {"relpath":"descriptor.yaml","sha256":"<64 lowercase hex>","content_base64":"<exact bytes>"},
  {"relpath":"pipeline.json","sha256":"<64 lowercase hex>","content_base64":"<exact bytes>"}
]}
```

Only `descriptor.yaml`, `pipeline.json`, and optional `card.md` are admitted.
File entries and the envelope forbid additional keys. Original bytes, line endings,
recipe mapping order, parameters, search blocks and asserted provenance are retained;
no recipe is converted, reserialized, imported, executed or expanded as code.

The first failure wins, in this order:

1. Front door and bounded body.
2. Wire schema: 400 `invalid_request` (including duplicate envelope JSON keys).
3. Any non-`descriptor.yaml` filename ending in `.yaml`/`.yml`, case insensitive:
   422 `recipe_format_unsupported`.
4. Any filename ending in `.n4a`, case insensitive: 422 `fitted_unsupported`.
5. Other non-admitted names, duplicates or missing required files:
   422 `undeclared_file` (including `pipeline.JSON`, nested paths and client manifests).
6. Invalid base64 or SHA mismatch: 422 `digest_mismatch`; decoded file limit: 413.
7. Shared owner descriptor bytes guard and model validation, including ID length
   over 128 or version outside `[0-9A-Za-z][0-9A-Za-z.+_-]{0,63}`:
   422 `invalid_descriptor`.
8. Descriptor `recipe.path` other than exactly `pipeline.json`:
   422 `recipe_format_unsupported`.
9. The claim table below.
10. Strict UTF-8 and the existing owner JSON recipe parser (duplicates, nonfinite,
    overflow, BOM, trailing content and recursion failures): 422
    `recipe_not_strict_json`. Unpaired surrogates receive that same refusal.
11. Iterative recipe caps, depth 64 (root depth zero) and 100000 nodes including
    mapping keys: 422 `recipe_limits_exceeded`.
12. Staged `validate_pipeline(stage, id, strict=False, extra_allowlist=())`:
    422 `security_refused` for scanner findings, otherwise `recipe_structure_invalid`.

Every `recipe_format_unsupported` response is exactly:

```json
{"error":"recipe_format_unsupported","accepted_recipe_files":["pipeline.json"],"conversion":"not_performed"}
```

| Submitted claim | 422 code |
| --- | --- |
| `governance.status` other than `draft` | `server_owned_field` |
| `governance.trust: official` | `server_owned_field` |
| Evaluation status other than `unvalidated`, or `validated_at` set | `server_owned_field` |
| Nonempty `provenance.fingerprints` | `server_owned_field` |
| `kind: fitted` or any artifact in an otherwise model-valid descriptor | `fitted_unsupported` |

R2's model-validation step precedes the claim table: an inconsistent fitted descriptor
with no artifacts, or a recipe descriptor declaring artifacts, fails earlier as
`invalid_descriptor`. The only legal descriptor visibility, `public`, is accepted
as inert asserted metadata. Record `scope: project` is authoritative. The two official
seed presets require new draft declarations before project ingestion. The environment
allowlist cannot widen this service's scanner. Static admission is not a sandbox or
functional validation.

Steps 2–11 create no staging or record directories. Failed staged validation cleans
up its staging directory. Refused bytes are not retained. User YAML and `.n4a` are
refused, not converted. This is an owner admission limit, not a claim those are
invalid sources. User JSON, YAML and `.n4a` replay integration through nirs4all and
dag-ml remains open, with no owner integration decision or execution qualification.

## Immutable storage and reads

`record_id` is SHA256 of the UTF-8 concatenation
`"nirs4all-repository/project-record/v1\0" + id + "\0" + version`.
`content_sha256` is SHA256 of canonical JSON over sorted `[relpath, sha256]` pairs
(compact separators, UTF-8, no nonfinite numbers). It includes all submitted files
and excludes project, principal, time and generated files. Different formatting is
different content. Same ID/version/bytes returns the first record and original
stamps; changed bytes return 409 `pipeline_version_conflict`.

```text
<store>/projects/<principal.project_id>/
  staging/<random>/
  records/<record_id>/
    record.json
    pipelines/<id>/
      descriptor.yaml
      pipeline.json
      card.md                         optional
      manifest.json                   generated by Repository owner
      ro-crate-metadata.json          generated by Repository owner
```

Intake first checks existing identity and disk space. It writes exact bytes in staging,
validates, calls `write_manifests`, rechecks submitted digests, writes `record.json`,
fsyncs every file and directory, and publishes with one atomic rename. Readers never
scan staging. Concurrent rename losers read the winner and return idempotence or
conflict; no mutable shared index exists. Abandoned staging from a process crash is
invisible and may be removed by the operator while the service is stopped.

Record metadata contains `schema`, `record_id`, `content_sha256`, `project_id`,
`stored_by` (principal ID, never credential), `stored_at`, `pipeline_id`,
`pipeline_version`, `framework`, `kind`, `task`, `recipe_format`, `files` (sorted
`relpath`, `sha256`, `size_bytes`) and `execution_requirements`, copied verbatim from
the generated manifest with all unknown dimensions retained. Its fixed claims are:

| Field | Server value |
| --- | --- |
| `schema` | `nirs4all-repository/project-record/v1` |
| `scope` | `project` |
| `provenance_status`, `rights_status` | `asserted_unverified` |
| `static_validation` | `passed_at_ingest` |
| `functional_validation` | `not_run` |
| `execution_status` | `not_executed` |
| `publication_status` | `not_published` |

List and add responses contain metadata with file digests; GET record adds
`content_base64` to every source-file entry. Reads verify internal structure and
digests, including consistency with the generated manifest and RO-Crate, without
reapplying current ingestion limits or owner descriptor schema. Corrupt records
appear in list as `{"record_id":"…","error":"corrupt_record"}`; direct retrieval
returns 409 `corrupt_record`. An unusable project namespace returns 409
`corrupt_project`. A corrupt foreign namespace never blocks another project.

`record.json` metadata relies on the trusted operator and filesystem. Its descriptive
fields are not cryptographically bound to the descriptor: changing nonempty
`stored_by`, `task` or `framework` strings directly on disk can still yield a 200
response. Source-file digests do not authenticate those metadata claims. The read
checks provide source-byte integrity and internal structural consistency, not
protection against an operator rewriting metadata or proof of its provenance.

## Dedicated client

```python
from pathlib import Path
from nirs4all_repository.project_client import ProjectClient

# Token comes from NIRS4ALL_PROJECT_TOKEN, or a private regular 0600 token_file.
client = ProjectClient("http://127.0.0.1:8123", token_file=Path("/private/token"))
added = client.add(Path("/private/bundle"))
records = client.list()
record_id = added["record"]["record_id"]
record = client.record(record_id)
pipeline = client.materialize(record_id, Path("/private/new-destination"))
pipeline.verify()
```

The environment token takes precedence. URLs must be loopback HTTP with an explicit
port and no userinfo, path, query or fragment. Proxies and redirects are disabled;
a redirect raises `ProjectClientError` without forwarding the bearer. HTTP refusals
are available in its `status` and structured `response`, not in exception text.
`add` reads the declared recipe unchanged, so YAML reaches the server for an explicit
refusal. Generated local manifests are excluded. `materialize` verifies source
hashes, recreates owner manifests, and returns `Pipeline` directly; it never resolves
a public name. The destination must be new. Neither client nor service is exported
through the frozen package `__all__`.

`ProjectClientError` covers transport failures, HTTP refusals and invalid remote
responses. Local bundle and destination operations retain their Python/owner
exceptions: `add` can raise `OSError` (including `FileNotFoundError` or
`PermissionError`), `ValueError` for an invalid path or non-regular source, and owner
`CatalogError` (including `DescriptorSyntaxError`) or Pydantic `ValidationError`
for an invalid local descriptor. After remote validation, `materialize` can raise
`OSError`, including `FileExistsError` for an existing destination,
`FileNotFoundError` for a missing parent, or `PermissionError`; owner manifest and
verification failures can raise `RecipeError` or `BridgeError`. These local errors
may contain local paths and are not normalized to `ProjectClientError`. A failed
local materialization may leave a partial destination; the caller handles it.

## Qualification

Run the owner/offline suite in the normal package environment. Without the optional
access leaf, the two service test modules (`test_project_service.py` and
`test_project_loopback.py`) use `pytest.importorskip`; all owner descriptor tests
still run. The existing CI-shaped command remains:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -m "not network and not evaluate"
```

The mandatory POSIX service qualification gate must explicitly set
`N4R_REQUIRE_PROJECT_SERVICE=1` and use the qualified installed access leaf and
Uvicorn environment. In that mode the test modules import the leaf directly;
missing dependencies must fail, and the full gate must report **zero skips**.
Loopback tests use `N4R_SERVICE_PYTHON` (default: current Python) for Uvicorn,
with WebSocket support for negative control D. For example, using existing
qualified environments without installing anything:

```bash
N4R_REQUIRE_PROJECT_SERVICE=1 \
PYTHONPATH="src:/path/to/qualified-access/site-packages" \
N4R_SERVICE_PYTHON=/path/to/qualified-uvicorn/bin/python \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
.venv/bin/python -m pytest -ra
```

Also verify the negative case: the required mode with the leaf absent fails
collection rather than skipping service tests. POSIX-only service tests are skipped
on Windows; Windows is not a supported required service qualification environment.

The real subprocess matrix repeats 17 hostile raw-loopback requests, including
valid bearer plus a genuine throwaway token under an arbitrary query key, full,
secret and percent-encoded token scans, a query sentinel in an injected owner failure,
malformed requests and disabled WebSocket upgrades. Production must have no leaks,
no 101 and no WebSocket scope. Deliberately unsafe test-only B/D/F profiles must leak
to validate the detector. They cannot be selected through the product CLI or `serve`.
Raw negative-control logs contain throwaway credentials and belong only in private
evidence storage. No evidence supports another Uvicorn version, remote hosting,
Windows service operation, public delivery or ecosystem migration completion.
