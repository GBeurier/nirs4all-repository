# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Optional service tests; the required qualification gate never skips the leaf."""
from __future__ import annotations

import asyncio
import base64
import copy
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

if sys.platform == "win32":
    pytest.skip("The project service requires POSIX", allow_module_level=True)

if os.environ.get("N4R_REQUIRE_PROJECT_SERVICE") == "1":
    import nirs4all_access as access
else:
    access = pytest.importorskip("nirs4all_access")

from nirs4all_repository.project_protocol import BODY_LIMIT, CLAIMS, SUBMISSION_SCHEMA, Refusal, digest, parse_submission
from nirs4all_repository.project_service import ProjectService, create_app
from nirs4all_repository.project_store import ProjectStore


def principal(project="a", who="writer", rights=("repository.read", "repository.add")):
    return access.ProjectPrincipal(project, who, frozenset({r.split(".")[0] for r in rights}), frozenset(rights))


def encoded(files):
    return json.dumps({"schema": SUBMISSION_SCHEMA, "files": [
        {"relpath": n, "sha256": digest(raw), "content_base64": base64.b64encode(raw).decode("ascii")} for n, raw in files.items()
    ]}).encode()


def source_files(make_catalog, **kwargs):
    root = make_catalog(**kwargs)
    return {p.name: p.read_bytes() for p in (root / "pipelines" / "demo_pipe").iterdir()}


async def call(app, method="GET", path="/v1/records", *, token=None, raw=b"", headers=(), query=b"", events=None, forbid_read=False):
    hs = list(headers)
    if token is not None:
        hs.append((b"authorization", ("Bearer " + token).encode()))
    if method == "POST" and not any(k.lower() == b"content-type" for k, v in hs):
        hs.append((b"content-type", b"application/json"))
    sent, receives = [], []
    queue = list(events) if events is not None else [{"type": "http.request", "body": raw}]

    async def receive():
        receives.append(True)
        if forbid_read:
            raise AssertionError("body read before refusal")
        return queue.pop(0)

    await app({"type": "http", "method": method, "path": path, "headers": hs, "query_string": query}, receive, _sender(sent))
    status = sent[0]["status"]
    return status, json.loads(sent[1]["body"]), sent[0]["headers"], len(receives)


def _sender(sent):
    async def send(event):
        sent.append(event)
    return send


@pytest.fixture
def service(tmp_path):
    token, credential = access.issue_credential(principal())
    app = ProjectService(ProjectStore(tmp_path / "service"), access.ProjectTokenVerifier([credential]))
    return app, token


def test_auth_rights_exact_errors_and_no_body_reads(tmp_path):
    good, c = access.issue_credential(principal())
    read, r = access.issue_credential(principal(who="reader", rights=("repository.read",)))
    other, o = access.issue_credential(principal(who="other", rights=("datasets.read",)))
    expired, e = access.issue_credential(principal(who="expired"), expires_at=time.time() - 1)
    revoked, v = access.issue_credential(principal(who="revoked"))
    app = ProjectService(ProjectStore(tmp_path / "service"), access.ProjectTokenVerifier([c, r, o, e, replace(v, revoked=True)]))
    for token in (None, "broken", access.generate_token(), good[:-1] + ("0" if good[-1] != "0" else "1"), expired, revoked):
        for method, path in (("POST", "/v1/records"), ("GET", "/v1/records"), ("GET", "/v1/records/" + "f" * 64), ("DELETE", "/unknown")):
            st, body, hs, n = asyncio.run(call(app, method, path, token=token, forbid_read=True))
            assert (st, body, n) == (401, {"error": "invalid_credential"}, 0)
            assert (b"www-authenticate", b"Bearer") in hs and (b"connection", b"close") in hs
    for token, expected in ((read, {"error": "missing_rights", "missing_rights": ["repository.add"]}), (other, {"error": "service_not_granted"})):
        st, body, _, n = asyncio.run(call(app, "POST", token=token, forbid_read=True))
        assert (st, body, n) == (403, expected, 0)
    for extra in ([(b"authorization", ("Bearer " + good).encode())], [(b"Authorization", b"broken")]):
        assert asyncio.run(call(app, "POST", token=good, headers=extra, forbid_read=True))[0] == 401
    assert asyncio.run(call(app, "GET", "/unknown", token=good, query=b"note=secret", forbid_read=True))[:2] == (404, {"error": "not_found"})


def test_front_door_order_media_limits_and_websocket(service):
    app, token = service
    cases = [
        ({"query": b"arbitrary=secret"}, 400),
        ({"headers": [(b"X-Project-ID", b"b")]}, 400),
        ({"headers": [(b"content-encoding", b"gzip")]}, 415),
        ({"headers": [(b"content-type", b"text/plain")]}, 415),
        ({"headers": [(b"content-length", b"1"), (b"transfer-encoding", b"chunked")]}, 400),
        ({"headers": [(b"content-length", str(BODY_LIMIT + 1).encode())]}, 413),
    ]
    for kwargs, status in cases:
        assert asyncio.run(call(app, "POST", token=token, forbid_read=True, **kwargs))[0] == status
    assert asyncio.run(call(app, "POST", token=token, events=[{"type": "http.request", "body": b"x" * (BODY_LIMIT + 1), "more_body": True}]))[0] == 413
    sent = []
    asyncio.run(app({"type": "websocket"}, None, _sender(sent)))
    assert sent == [{"type": "websocket.close", "code": 1008}]


def test_body_deadline_and_catch_owner_failure(service, monkeypatch):
    app, token = service
    app.body_deadline = .01
    async def receive():
        await asyncio.sleep(.1)
        return {"type": "http.request", "body": b""}
    sent = []
    asyncio.run(app({"type": "http", "method": "POST", "path": "/v1/records", "headers": [(b"authorization", ("Bearer " + token).encode()), (b"content-type", b"application/json")]}, receive, _sender(sent)))
    assert sent[0]["status"] == 408
    def fail(*args):
        raise RuntimeError("PRIVATE_SENTINEL " + token)
    monkeypatch.setattr(app.store, "list", fail)
    assert asyncio.run(call(app, token=token))[:2] == (500, {"error": "internal_error"})


def test_exact_bytes_provenance_requirements_and_foreign_404(service, make_catalog):
    app, token = service
    files = source_files(make_catalog)
    # Keep tree order, params strings, root search metadata and source whitespace.
    files["pipeline.json"] = b'{ "pipeline":[{"model":{"class":"sklearn.linear_model.Ridge","params":{"label":"numpy.float64","z":1,"a":2}}}], "search":{"z":[2,1],"a":0}, "provenance":{"source":"asserted"} }\r\n'
    raw = encoded(files)
    st, result, _, _ = asyncio.run(call(app, "POST", token=token, raw=raw))
    assert st == 201
    record = result["record"]
    assert all(record[k] == v for k, v in CLAIMS.items())
    assert len(record["execution_requirements"]["unknown"]) == 5
    rid = record["record_id"]
    st, loaded, _, _ = asyncio.run(call(app, path="/v1/records/" + rid, token=token))
    assert st == 200
    assert {f["relpath"]: base64.b64decode(f["content_base64"]) for f in loaded["files"]} == files
    assert asyncio.run(call(app, "POST", token=token, raw=raw))[:2] == (200, {"status": "already_present", "record": record})
    files["pipeline.json"] += b" "
    assert asyncio.run(call(app, "POST", token=token, raw=encoded(files)))[:2] == (409, {"error": "pipeline_version_conflict"})
    foreign_token, credential = access.issue_credential(principal("b"))
    foreign = ProjectService(app.store, access.ProjectTokenVerifier([credential]))
    unknown = asyncio.run(call(foreign, path="/v1/records/" + "0" * 64, token=foreign_token))
    assert asyncio.run(call(foreign, path="/v1/records/" + rid, token=foreign_token))[:3] == unknown[:3]
    assert unknown[0:2] == (404, {"error": "not_found"})
    assert asyncio.run(call(foreign, token=foreign_token))[1] == {"records": []}
    assert asyncio.run(call(foreign, "POST", token=foreign_token, raw=raw))[0] == 201


@pytest.mark.parametrize("name,code", [
    ("pipeline.yaml", "recipe_format_unsupported"), ("pipeline.yml", "recipe_format_unsupported"), ("pipeline.YAML", "recipe_format_unsupported"),
    ("pipeline.n4a", "fitted_unsupported"), ("pipeline.N4A", "fitted_unsupported"),
    ("pipeline.JSON", "undeclared_file"), ("sub/pipeline.json", "undeclared_file"),
    ("manifest.json", "undeclared_file"), ("evil.pkl", "undeclared_file"), (".git/x", "undeclared_file"), ("a\\b", "undeclared_file"), ("CON", "undeclared_file"),
])
@pytest.mark.parametrize("recipe", [b"pipeline: [x]\n", b'["sklearn.linear_model.Ridge"]'])
def test_exact_file_refusals_no_staging(service, make_catalog, name, code, recipe):
    app, token = service
    files = source_files(make_catalog)
    files[name] = recipe
    if name.startswith("pipeline.") or name == "sub/pipeline.json":
        files.pop("pipeline.json", None)
    st, body, _, _ = asyncio.run(call(app, "POST", token=token, raw=encoded(files)))
    assert st == 422 and body["error"] == code
    if code == "recipe_format_unsupported":
        assert body == {"error": code, "accepted_recipe_files": ["pipeline.json"], "conversion": "not_performed"}
    assert not list(app.store.root.rglob("record.json"))
    assert not (app.store.root / "projects").exists()


@pytest.mark.parametrize("raw,code", [
    (b"pipeline: [x]", "recipe_not_strict_json"),
    (b'{"pipeline":[],"pipeline":[{"class":"sklearn.linear_model.Ridge"}]}', "recipe_not_strict_json"),
    (b'{"pipeline":[{"class":"os.system","class":"sklearn.linear_model.Ridge"}]}', "recipe_not_strict_json"),
    (b"[NaN]", "recipe_not_strict_json"), (b"[1e999]", "recipe_not_strict_json"),
    (b'["\\ud800"]', "recipe_not_strict_json"),
    (b"[" * 65 + b"0" + b"]" * 65, "recipe_limits_exceeded"),
    (b"[" + b"0," * 100000 + b"0]", "recipe_limits_exceeded"),
    (b'{"pipeline":[{"class":"os.system"}]}', "security_refused"),
    (b'{"pipeline":[{"model":{"class":"sklearn.linear_model.Ridge","params":{"func":{"function":"builtins.eval"}}}}]}', "security_refused"),
    (b'{"pipeline":[]}', "recipe_structure_invalid"),
])
def test_recipe_refusals_cleanup(service, make_catalog, monkeypatch, raw, code):
    app, token = service
    monkeypatch.setenv("NIRS4ALL_REPOSITORY_ALLOWLIST", "os,builtins")
    files = source_files(make_catalog)
    files["pipeline.json"] = raw
    assert asyncio.run(call(app, "POST", token=token, raw=encoded(files)))[:2] == (422, {"error": code})
    assert not list(app.store.root.rglob("record.json"))
    assert not list(app.store.root.glob("projects/*/staging/*"))


@pytest.mark.parametrize("suffix", [b'governance: {status: published}\ngovernance: {status: draft}\n', b"description: .nan\n", b"description: &a [0]\ntags: *a\n", b"description: !!binary aGk=\n", b"governance: {<<: {status: published}, status: draft}\n", b'description: "\\ud800"\n', b"description: 1:30.5\n", b"updated_at: 2026-13-45\n"])
def test_http_owner_guard_constant_refusal(service, make_catalog, suffix):
    app, token = service
    files = source_files(make_catalog)
    files["descriptor.yaml"] += suffix
    assert asyncio.run(call(app, "POST", token=token, raw=encoded(files)))[:2] == (422, {"error": "invalid_descriptor"})
    assert not (app.store.root / "projects").exists()


@pytest.mark.parametrize("update", [
    {"governance": {"status": "published", "trust": "community"}},
    {"governance": {"status": "draft", "trust": "official"}},
    {"reference": {"source": "nirs4all-datasets", "name": "example"}, "evaluation": {"metric": "rmse", "status": "validated"}},
    {"reference": {"source": "nirs4all-datasets", "name": "example"}, "evaluation": {"metric": "rmse", "validated_at": "2026-11-04"}},
    {"provenance": {"fingerprints": {"config_sha256": "0" * 64}}},
])
def test_claim_refusal_table(service, make_catalog, update):
    app, token = service
    files = source_files(make_catalog, descriptor_overrides=update)
    assert asyncio.run(call(app, "POST", token=token, raw=encoded(files)))[:2] == (422, {"error": "server_owned_field"})
    assert not (app.store.root / "projects").exists()


def test_closed_schema_digest_order_and_descriptor_path(service, make_catalog):
    app, token = service
    files = source_files(make_catalog)
    body = json.loads(encoded(files))
    for field, value in (("project_id", "b"), ("scope", "public"), ("schema", "forged")):
        forged = {**body, field: value}
        assert asyncio.run(call(app, "POST", token=token, raw=json.dumps(forged).encode()))[0:2] == (400, {"error": "invalid_request"})
    duplicated = copy.deepcopy(body)
    duplicated["files"].append(duplicated["files"][0])
    assert asyncio.run(call(app, "POST", token=token, raw=json.dumps(duplicated).encode()))[1] == {"error": "undeclared_file"}
    bad = copy.deepcopy(body)
    bad["files"][0]["sha256"] = "0" * 64
    assert asyncio.run(call(app, "POST", token=token, raw=json.dumps(bad).encode()))[1] == {"error": "digest_mismatch"}
    files["descriptor.yaml"] = files["descriptor.yaml"].replace(b"path: pipeline.json", b"path: manifest.json")
    assert asyncio.run(call(app, "POST", token=token, raw=encoded(files)))[1] == {"error": "recipe_format_unsupported", "accepted_recipe_files": ["pipeline.json"], "conversion": "not_performed"}
    assert not (app.store.root / "projects").exists()


def test_concurrent_adds_stamps_and_conflicting_bytes(service, make_catalog):
    app, _ = service
    files = source_files(make_catalog)
    one = parse_submission(encoded(files))
    files["pipeline.json"] += b" "
    two = parse_submission(encoded(files))
    def add(i):
        try:
            return app.store.add(principal(who="writer" + str(i)), one if i % 2 else two)
        except Refusal as exc:
            return exc.status, exc.body
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(add, range(16)))
    assert sum(status == 201 for status, _ in results) == 1
    assert all(status in (200, 201, 409) for status, _ in results)
    winners = [body["record"] for status, body in results if status in (200, 201)]
    assert len(winners) == 8
    assert all(record == winners[0] for record in winners)
    assert not list(app.store.root.glob("projects/*/staging/*"))
    with ThreadPoolExecutor(max_workers=16) as pool:
        replay = list(pool.map(lambda _: app.store.add(principal(), one if winners[0]["content_sha256"] == one.content_sha256 else two), range(16)))
    assert all(st == 200 and value["record"] == winners[0] for st, value in replay)


def test_corrupt_foreign_symlink_and_crash_staging_isolation(service, make_catalog):
    app, _ = service
    sub = parse_submission(encoded(source_files(make_catalog)))
    _, added = app.store.add(principal(), sub)
    project_b = app.store.root / "projects/b"
    project_b.symlink_to(app.store.root / "projects/a", target_is_directory=True)
    assert app.store.list("a") == [added["record"]]
    with pytest.raises(Refusal, match="corrupt"):
        app.store.list("b")
    orphan = app.store.root / "projects/a/staging/abandoned"
    orphan.mkdir()
    (orphan / "record.json").write_text("incomplete")
    assert len(app.store.list("a")) == 1
    record = app.store.root / "projects/a/records" / sub.record_id
    (record / "pipelines/demo_pipe/pipeline.json").write_bytes(b"tampered")
    assert app.store.list("a") == [{"record_id": sub.record_id, "error": "corrupt_record"}]
    assert app.store.list("unknown") == []


def test_fault_before_rename_cleanup_and_recovery(service, make_catalog, monkeypatch):
    import nirs4all_repository.project_store as module
    app, _ = service
    sub = parse_submission(encoded(source_files(make_catalog)))
    original = module.fsync_tree
    def fail(*a):
        raise RuntimeError("PRIVATE_OWNER_FAILURE")
    monkeypatch.setattr(module, "fsync_tree", fail)
    with pytest.raises(RuntimeError):
        app.store.add(principal(), sub)
    assert app.store.list("a") == []
    assert not list(app.store.root.glob("projects/*/staging/*"))
    monkeypatch.setattr(module, "fsync_tree", original)
    assert app.store.add(principal(), sub)[0] == 201


def test_floor_and_startup_closed(tmp_path, make_catalog, monkeypatch):
    import nirs4all_repository.project_store as module
    store = ProjectStore(tmp_path / "service")
    sub = parse_submission(encoded(source_files(make_catalog)))
    usage = module.shutil.disk_usage(store.root)
    monkeypatch.setattr(module.shutil, "disk_usage", lambda _: usage._replace(free=2_147_483_647))
    with pytest.raises(Refusal, match="insufficient_storage"):
        store.add(principal(), sub)
    assert not (store.root / "projects").exists()
    cred = tmp_path / "credentials.json"
    for credentials in ([], [access.issue_credential(principal(rights=("repository.admin",)))[1]], [access.issue_credential(principal(), expires_at=0)[1]]):
        access.write_credential_store(cred, credentials)
        with pytest.raises(ValueError, match="no active"):
            create_app(store.root, cred)
    access.write_credential_store(cred, [access.issue_credential(principal())[1]])
    for host in ("0.0.0.0", "192.0.2.1", "127.1"):
        with pytest.raises(ValueError):
            create_app(store.root, cred, host=host)
    with pytest.raises(ValueError):
        ProjectStore(tmp_path / "catalog_root" / "bad_store")


def test_26_catalogue_admission(service, repo_root):
    app, token = service
    counts = {201: 0, 422: 0}
    for bundle in sorted((repo_root / "pipelines").iterdir()):
        if not bundle.is_dir():
            continue
        files = {p.name: p.read_bytes() for p in bundle.iterdir() if p.name in {"descriptor.yaml", "pipeline.json", "card.md"}}
        status, body, _, _ = asyncio.run(call(app, "POST", token=token, raw=encoded(files)))
        counts[status] += 1
        if status == 422:
            assert body == {"error": "server_owned_field"}
    assert counts == {201: 24, 422: 2}


def test_bomb_refused_while_health_responds(service, make_catalog):
    app, token = service
    files = source_files(make_catalog)
    # Reproduce the review's 656-byte expansion-bomb mechanism, with a
    # synthetic minimal descriptor and an eight-level nine-way alias graph.
    descriptor = {"schema_version": 1, "id": "p", "name": "N", "summary": "s", "framework": "nirs4all", "kind": "recipe", "task": "regression",
                      "version": "1.0.0", "license": "MIT", "created_at": "2026-11-04", "authors": [{"name": "a"}],
                      "recipe": {"format": "nirs4all/pipeline-config", "path": "pipeline.json"}}
    import yaml
    lines = ["a0: &a0 [x]"] + [f"a{i}: &a{i} [" + ",".join([f"*a{i-1}"] * 9) + "]" for i in range(1, 8)]
    bomb = ("\n".join(lines) + "\n" + yaml.safe_dump(descriptor, sort_keys=False)).encode()
    assert len(bomb) <= 656
    files["descriptor.yaml"] = bomb + b" " * (656 - len(bomb))
    assert len(files["descriptor.yaml"]) == 656
    async def exercise():
        start = time.monotonic()
        bomb = asyncio.create_task(call(app, "POST", token=token, raw=encoded(files)))
        health = asyncio.create_task(call(app, path="/healthz"))
        result, live = await asyncio.gather(bomb, health)
        assert result[:2] == (422, {"error": "invalid_descriptor"})
        assert live[:2] == (200, {"status": "ok"})
        assert time.monotonic() - start < 1
    asyncio.run(exercise())


def test_offline_import_and_cli_closed():
    code = "import sys,nirs4all_repository; assert 'nirs4all_access' not in sys.modules; assert 'uvicorn' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)
    command = [sys.executable, "-m", "nirs4all_repository.project_service"]
    assert subprocess.run(command + ["--help"], capture_output=True).returncode == 0
    for flag in ("--tls", "--proxy", "--log-level", "--ws", "--http", "--access-log"):
        assert subprocess.run(command + ["serve", flag], capture_output=True).returncode != 0


def test_fitted_artifact_refusal_and_model_precedence(service, make_catalog):
    app, token = service
    artifact = {"name": "model", "backend": "n4a", "relpath": "model.n4a", "sha256": "0" * 64, "size_bytes": 0}
    files = source_files(make_catalog, descriptor_overrides={"kind": "fitted", "artifacts": [artifact]})
    assert asyncio.run(call(app, "POST", token=token, raw=encoded(files)))[:2] == (422, {"error": "fitted_unsupported"})
    # R2 step 7 explicitly validates the owner model before step 9's claim table.
    # An internally inconsistent fitted descriptor fails that earlier boundary.
    import yaml
    descriptor = yaml.safe_load(files["descriptor.yaml"])
    descriptor["artifacts"] = []
    files["descriptor.yaml"] = yaml.safe_dump(descriptor).encode()
    assert asyncio.run(call(app, "POST", token=token, raw=encoded(files)))[:2] == (422, {"error": "invalid_descriptor"})
    assert not (app.store.root / "projects").exists()


def test_file_limit_and_size_identity_bounds(service, make_catalog):
    app, token = service
    files = source_files(make_catalog)
    files["card.md"] = b"x" * ((512 << 10) + 1)
    assert asyncio.run(call(app, "POST", token=token, raw=encoded(files)))[:2] == (413, {"error": "file_too_large"})
    files.pop("card.md")
    import yaml
    descriptor = yaml.safe_load(files["descriptor.yaml"])
    for key, value in (("version", "../../x"), ("version", ""), ("version", "x" * 65), ("id", "x" * 129)):
        changed = {**descriptor, key: value}
        files["descriptor.yaml"] = yaml.safe_dump(changed).encode()
        assert asyncio.run(call(app, "POST", token=token, raw=encoded(files)))[:2] == (422, {"error": "invalid_descriptor"})
    assert not (app.store.root / "projects").exists()


def test_same_identity_different_search_content_conflicts(service, make_catalog):
    app, token = service
    files = source_files(make_catalog)
    recipe = json.loads(files["pipeline.json"])
    recipe["search"] = {"choices": [1, 2]}
    files["pipeline.json"] = json.dumps(recipe).encode()
    assert asyncio.run(call(app, "POST", token=token, raw=encoded(files)))[0] == 201
    recipe["search"]["choices"] = [2, 1]
    files["pipeline.json"] = json.dumps(recipe).encode()
    assert asyncio.run(call(app, "POST", token=token, raw=encoded(files)))[:2] == (409, {"error": "pipeline_version_conflict"})


def test_sixteen_initial_identical_adds_have_one_winner(service, make_catalog):
    app, _ = service
    submission = parse_submission(encoded(source_files(make_catalog)))
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda i: app.store.add(principal(who="writer" + str(i)), submission), range(16)))
    assert sorted(st for st, _ in results) == [200] * 15 + [201]
    assert all(body["record"] == results[0][1]["record"] for _, body in results)


@pytest.mark.parametrize("target", ["record.json", "pipelines/demo_pipe/manifest.json", "pipelines/demo_pipe/ro-crate-metadata.json", "pipelines/demo_pipe/pipeline.json"])
def test_corrupt_and_symlink_records_flagged_without_foreign_effect(service, make_catalog, target):
    app, _ = service
    submission = parse_submission(encoded(source_files(make_catalog)))
    app.store.add(principal("a"), submission)
    app.store.add(principal("b"), submission)
    base = app.store.root / "projects/b/records" / submission.record_id
    path = base / target
    path.write_bytes(b"{broken")
    assert app.store.list("b") == [{"record_id": submission.record_id, "error": "corrupt_record"}]
    assert app.store.read("a", submission.record_id)["pipeline_id"] == "demo_pipe"
    path.unlink()
    path.symlink_to(app.store.root / "projects/a/records" / submission.record_id / target)
    assert app.store.list("b") == [{"record_id": submission.record_id, "error": "corrupt_record"}]
    assert app.store.read("a", submission.record_id)["pipeline_id"] == "demo_pipe"


def test_filename_refusal_precedes_digest_and_descriptor(service, make_catalog):
    app, token = service
    files = source_files(make_catalog)
    files["descriptor.yaml"] = b"broken descriptor"
    files["unknown.bin"] = b"unadmitted"
    files["model.N4A"] = b"unadmitted"
    files["pipeline.YAML"] = b"unadmitted"
    body = json.loads(encoded(files))
    for entry in body["files"]:
        entry["sha256"] = "invalid"
    expected = ["recipe_format_unsupported", "fitted_unsupported", "undeclared_file", "digest_mismatch"]
    for index, code in enumerate(expected):
        result = asyncio.run(call(app, "POST", token=token, raw=json.dumps(body).encode()))
        assert result[1]["error"] == code
        if index < 3:
            removal = ("pipeline.YAML", "model.N4A", "unknown.bin")[index]
            body["files"] = [entry for entry in body["files"] if entry["relpath"] != removal]
    assert not (app.store.root / "projects").exists()


@pytest.mark.parametrize("failure", ["staging", "records", "mkdtemp"])
def test_setup_enospc_returns_507_without_payload_writes(service, make_catalog, monkeypatch, failure):
    import errno

    import nirs4all_repository.project_store as module

    app, token = service
    raw = encoded(source_files(make_catalog))
    namespace = app.store.root / "projects/a"
    for name in ("staging", "records"):
        (namespace / name).mkdir(parents=True)
    before = sorted(path.relative_to(app.store.root) for path in app.store.root.rglob("*"))
    original = module.directory

    def fail_directory(path, *, create=False):
        if create and path.name == failure:
            raise OSError(errno.ENOSPC, "simulated full disk")
        return original(path, create=create)

    def fail_mkdtemp(*args, **kwargs):
        raise OSError(errno.ENOSPC, "simulated full disk")

    if failure == "mkdtemp":
        monkeypatch.setattr(module.tempfile, "mkdtemp", fail_mkdtemp)
    else:
        monkeypatch.setattr(module, "directory", fail_directory)
    assert asyncio.run(call(app, "POST", token=token, raw=raw))[:2] == (507, {"error": "insufficient_storage"})
    assert sorted(path.relative_to(app.store.root) for path in app.store.root.rglob("*")) == before
    assert not any(path.is_file() for path in app.store.root.rglob("*"))
