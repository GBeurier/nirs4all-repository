# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Real subprocess raw-loopback gate, including mandatory leaking controls B/D/F."""
from __future__ import annotations

import base64
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

import pytest

if sys.platform == "win32":
    pytest.skip("The project service requires POSIX", allow_module_level=True)

if os.environ.get("N4R_REQUIRE_PROJECT_SERVICE") == "1":
    import nirs4all_access as access
else:
    access = pytest.importorskip("nirs4all_access")

from nirs4all_repository.project_client import ProjectClient, ProjectClientError

SERVER = Path(__file__).parent / "project_service_helpers/server.py"
PYTHON = os.environ.get("N4R_SERVICE_PYTHON", sys.executable)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def raw_request(port, data):
    with socket.create_connection(("127.0.0.1", port), timeout=2) as sock:
        sock.settimeout(.2)
        sock.sendall(data)
        result = bytearray()
        try:
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                result.extend(chunk)
        except (TimeoutError, ConnectionError):
            pass
        return bytes(result)


def start_server(tmp_path, profile, credentials, failure):
    port = free_port()
    logs = [tmp_path / (profile + ".stdout"), tmp_path / (profile + ".stderr")]
    seen = tmp_path / (profile + ".scopes")
    env = dict(os.environ, N4R_TEST_FAILURE=failure, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    with logs[0].open("wb") as out, logs[1].open("wb") as err:
        command = ([PYTHON, "-m", "nirs4all_repository.project_service", "serve", "--store", str(tmp_path / "store"),
                    "--credentials", str(credentials), "--port", str(port)] if profile == "CLI" else
                   [PYTHON, str(SERVER), str(credentials), str(tmp_path / "store"), str(port), profile, str(seen)])
        process = subprocess.Popen(command, stdout=out, stderr=err, env=env)
    for _ in range(200):
        if process.poll() is not None:
            raise AssertionError("subprocess failed to start; inspect private evidence")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=.1):
                return port, process, logs, seen
        except OSError:
            time.sleep(.025)
    process.kill()
    process.wait()
    raise AssertionError("subprocess startup timeout")


def stop_server(process):
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise AssertionError("subprocess shutdown timeout") from None
    assert process.returncode in (0, -signal.SIGINT)


def credentials_file(path):
    principal = access.ProjectPrincipal("proj-a", "writer", frozenset({"repository"}), frozenset({"repository.read", "repository.add"}))
    good, first = access.issue_credential(principal)
    victim, second = access.issue_credential(principal)
    access.write_credential_store(path, [first, second])
    return good, victim


def test_reviewer_17_case_raw_loopback_log_matrix(tmp_path):
    # Raw negative controls intentionally contain throwaway secrets. Retain them
    # only in a private evidence directory, never in test output or source files.
    evidence = Path(os.environ["N4R_SERVICE_EVIDENCE"]) if "N4R_SERVICE_EVIDENCE" in os.environ else tmp_path
    evidence.mkdir(parents=True, exist_ok=True, mode=0o700)
    evidence.chmod(0o700)
    credentials = evidence / "credentials.json"
    good, victim = credentials_file(credentials)
    full, secret = victim.encode(), victim.split(".")[2].encode()
    # quote() leaves dots unescaped, so also scan a fully percent-encoded token.
    encoded = b"".join(b"%%%02X" % c for c in full)
    forms = [full, secret, quote(victim, safe="").encode(), encoded, encoded.lower()]
    host = b"Host: 127.0.0.1\r\n"
    auth = b"Authorization: Bearer " + good.encode() + b"\r\n"
    ws = b"Connection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: " + base64.b64encode(b"x" * 16) + b"\r\n"
    query = b"?note=" + full
    cases = [
        ("bearer arbitrary key", b"GET /v1/records" + query + b" HTTP/1.1\r\n" + host + auth + b"\r\n", 400),
        ("bearer nested key", b"GET /v1/records?a=1&filter%5Bx%5D=" + encoded + b" HTTP/1.1\r\n" + host + auth + b"\r\n", 400),
        ("bearer bare value", b"GET /v1/records?" + secret + b" HTTP/1.1\r\n" + host + auth + b"\r\n", 400),
        ("missing bearer", b"GET /v1/records?access_token=" + full + b" HTTP/1.1\r\n" + host + b"\r\n", 401),
        ("health query", b"GET /healthz" + query + b" HTTP/1.1\r\n" + host + b"\r\n", 401),
        ("POST unread query body", b"POST /v1/records" + query + b" HTTP/1.1\r\n" + host + auth + b"Content-Length: 100000\r\nExpect: 100-continue\r\n\r\n", 400),
        ("unknown route query", b"GET /unknown" + query + b" HTTP/1.1\r\n" + host + auth + b"\r\n", 404),
        ("secret path", b"GET /v1/records/" + full + b" HTTP/1.1\r\n" + host + auth + b"\r\n", 404),
        ("websocket bearer", b"GET /v1/records" + query + b" HTTP/1.1\r\n" + host + auth + ws + b"\r\n", 400),
        ("websocket missing bearer", b"GET /ws?token=" + full + b" HTTP/1.1\r\n" + host + ws + b"\r\n", 401),
        ("h2c", b"GET /v1/records" + query + b" HTTP/1.1\r\n" + host + auth + b"Connection: Upgrade, HTTP2-Settings\r\nUpgrade: h2c\r\nHTTP2-Settings: AAMAAABkAAQAoAAAAAIAAAAA\r\n\r\n", 400),
        ("malformed version", b"GET /v1/records" + query + b" HTTP/9.9\r\n" + host + b"\r\n", 401),
        ("malformed space", b"GET /v1/records?a b=" + full + b" HTTP/1.1\r\n" + host + b"\r\n", 400),
        ("malformed NUL", b"GET /v1/records?x=\x00" + full + b" HTTP/1.1\r\n" + host + b"\r\n", 400),
        ("bad header", b"GET /v1/records" + query + b" HTTP/1.1\r\n" + host + b"Bad Header: " + full + b"\r\n\r\n", 400),
        ("oversized target", b"GET /v1/records?pad=" + b"a" * 70000 + b"&x=" + full + b" HTTP/1.1\r\n" + host + b"\r\n", 401),
        ("forced owner exception query sentinel", b"GET /boom?sentinel=PRIVATE_QUERY_SENTINEL&x=" + full + b" HTTP/1.1\r\n" + host + auth + b"\r\n", 500),
    ]
    version = subprocess.check_output([PYTHON, "-c", "import uvicorn;print(uvicorn.__version__)"], text=True).strip()
    summary = {"uvicorn_version": version, "cases": len(cases), "profiles": {}}
    # A/B/D/F are mandatory; the rest reproduce the original review's controls.
    profiles = "ABCDEFGH"
    if subprocess.run([PYTHON, "-c", "import httptools"], capture_output=True).returncode == 0:
        profiles += "I"
    for profile in profiles:
        port, process, logs, seen = start_server(evidence, profile, credentials, "PRIVATE_QUERY_SENTINEL " + victim)
        rows = []
        try:
            for label, data, expected in cases:
                response = raw_request(port, data)
                match = re.search(rb"HTTP/1.1 (\d+)", response)
                status = int(match[1]) if match else None
                if profile == "A":
                    assert status == expected, label
                    assert status != 101
                    assert b"100 Continue" not in response
                    assert b"PRIVATE_QUERY_SENTINEL" not in response
                assert not any(form in response for form in forms), "response leaked throwaway credential"
                (evidence / (profile + "-" + str(len(rows)) + ".response")).write_bytes(response)
                rows.append({"case": label, "status": status})
        finally:
            stop_server(process)
        all_logs = b"\n".join(p.read_bytes() for p in logs)
        leaking = [line for line in all_logs.splitlines() if any(form in line for form in forms)]
        scopes = seen.read_text().splitlines()
        if profile == "A":
            assert not leaking
            assert b"PRIVATE_QUERY_SENTINEL" not in all_logs and b"Traceback" not in all_logs
            assert "websocket" not in scopes
        if profile in "BDF":
            assert leaking, "negative control did not validate detector"
        summary["profiles"][profile] = {"leaking_lines": len(leaking), "websocket_scopes": scopes.count("websocket"), "requests": rows}
    # These are throwaway credentials, not production credentials. Disable the
    # retained hash-only snapshot after the gate; private raw controls stay intact.
    access.write_credential_store(credentials, [])
    (evidence / "matrix-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    for path in evidence.iterdir():
        if path.is_file():
            path.chmod(0o600)


def test_real_client_materialize_no_proxy_redirect_and_yaml(tmp_path, make_catalog, monkeypatch):
    credentials = tmp_path / "credentials.json"
    token, _ = credentials_file(credentials)
    port, process, logs, seen = start_server(tmp_path, "CLI", credentials, "PRIVATE_OWNER_SENTINEL")
    proxy_port = free_port()
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:" + str(proxy_port))
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:" + str(proxy_port))
    monkeypatch.setenv("no_proxy", "")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("NIRS4ALL_PROJECT_TOKEN", token)
    try:
        client = ProjectClient("http://127.0.0.1:" + str(port))
        bundle = make_catalog() / "pipelines/demo_pipe"
        added = client.add(bundle)
        rid = added["record"]["record_id"]
        assert len(client.list()) == 1
        original = (bundle / "pipeline.json").read_bytes()
        pipeline = client.materialize(rid, tmp_path / "materialized")
        pipeline.verify()
        assert pipeline.recipe() == json.loads(original)
        assert (pipeline.path / "pipeline.json").read_bytes() == original
        assert all((pipeline.path / n).read_bytes() == (bundle / n).read_bytes() for n in ("descriptor.yaml", "pipeline.json", "card.md"))
        descriptor = bundle / "descriptor.yaml"
        descriptor.write_bytes(descriptor.read_bytes().replace(b"pipeline.json", b"pipeline.yaml"))
        (bundle / "pipeline.json").rename(bundle / "pipeline.yaml")
        with pytest.raises(ProjectClientError) as refused:
            client.add(bundle)
        assert refused.value.status == 422
        assert refused.value.response == {"error": "recipe_format_unsupported", "accepted_recipe_files": ["pipeline.json"], "conversion": "not_performed"}
    finally:
        stop_server(process)
    assert not any(token.encode() in p.read_bytes() for p in logs)
    # A local redirect trap proves no second request and no forwarded bearer.
    with socket.socket() as trap:
        trap.bind(("127.0.0.1", 0))
        trap.listen()
        trap.settimeout(.3)
        from concurrent.futures import ThreadPoolExecutor
        def redirect():
            with trap.accept()[0] as connection:
                connection.recv(65536)
                connection.sendall(b"HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1:" + str(trap.getsockname()[1]).encode() + b"/captured\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(redirect)
            with pytest.raises(ProjectClientError) as error:
                ProjectClient("http://127.0.0.1:" + str(trap.getsockname()[1])).list()
            assert error.value.status == 302
            future.result()
        with pytest.raises(TimeoutError):
            trap.accept()


def test_client_private_file_and_invalid_urls(tmp_path, monkeypatch):
    monkeypatch.delenv("NIRS4ALL_PROJECT_TOKEN", raising=False)
    token_file = tmp_path / "token"
    token_file.write_text(access.generate_token())
    token_file.chmod(0o600)
    assert ProjectClient("http://localhost:8123", token_file=token_file)
    token_file.chmod(0o644)
    with pytest.raises(ProjectClientError, match="invalid_token_file"):
        ProjectClient("http://localhost:8123", token_file=token_file)
    monkeypatch.setenv("NIRS4ALL_PROJECT_TOKEN", access.generate_token())
    for url in ("http://example.org:80", "https://localhost:8123", "http://localhost:8123?token=x", "http://x@localhost:8123", "http://localhost:8123/#token=x"):
        with pytest.raises(ProjectClientError, match="invalid_loopback_url"):
            ProjectClient(url)


def test_real_http_owner_guard_no_staging_and_healthy_during_bomb(tmp_path, make_catalog, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    import yaml

    from nirs4all_repository.project_protocol import SUBMISSION_SCHEMA, digest

    credentials = tmp_path / "credentials.json"
    token, _ = credentials_file(credentials)
    port, process, logs, _ = start_server(tmp_path, "CLI", credentials, "PRIVATE_OWNER_SENTINEL")
    monkeypatch.setenv("NIRS4ALL_PROJECT_TOKEN", token)
    bundle = make_catalog() / "pipelines/demo_pipe"
    normal = (bundle / "descriptor.yaml").read_bytes()
    recipe = (bundle / "pipeline.json").read_bytes()
    client = ProjectClient("http://127.0.0.1:" + str(port))
    def submit(descriptor):
        body = {"schema": SUBMISSION_SCHEMA, "files": [
            {"relpath": n, "sha256": digest(raw), "content_base64": base64.b64encode(raw).decode()}
            for n, raw in (("descriptor.yaml", descriptor), ("pipeline.json", recipe))
        ]}
        with pytest.raises(ProjectClientError) as error:
            client._request("POST", "/v1/records", body)
        assert error.value.status == 422
        assert error.value.response == {"error": "invalid_descriptor"}
    try:
        for suffix in (b"governance: {status: published}\ngovernance: {status: draft}\n", b"description: .nan\n",
                       b"governance: {<<: {status: published}, status: draft}\n", b"description: !!binary aGk=\n",
                       b'description: "\\ud800"\n', b"description: 1:30.5\n", b"updated_at: 2026-13-45\n"):
            submit(normal + suffix)
        submit(b"\xff")
        minimal = yaml.safe_load(normal)
        minimal["id"] = "p"
        # Keep the production-boundary probe at the review's exact byte size.
        minimal.pop("provenance", None)
        minimal.pop("governance", None)
        minimal.pop("tags", None)
        minimal["summary"] = "s"
        minimal["name"] = "N"
        minimal["authors"] = [{"name": "a"}]
        lines = ["a0: &a0 [x]"] + [f"a{i}: &a{i} [" + ",".join([f"*a{i-1}"] * 9) + "]" for i in range(1, 8)]
        bomb = ("\n".join(lines) + "\n" + yaml.safe_dump(minimal, sort_keys=False)).encode()
        assert len(bomb) <= 656
        bomb += b" " * (656 - len(bomb))
        start = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as pool:
            bad = pool.submit(submit, bomb)
            health = pool.submit(raw_request, port, b"GET /healthz HTTP/1.1\r\nHost: localhost\r\n\r\n")
            assert b"200 OK" in health.result()
            bad.result()
        assert time.monotonic() - start < 1
        assert not (tmp_path / "store/projects").exists()
        # Authentication rejects before sending 100 Continue or waiting for bytes.
        response = raw_request(port, b"POST /v1/records HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: 1000000\r\nExpect: 100-continue\r\n\r\n")
        assert b"401 Unauthorized" in response and b"100 Continue" not in response
        assert client.add(bundle)["status"] == "created"
    finally:
        stop_server(process)
    assert not any(token.encode() in p.read_bytes() or b"Traceback" in p.read_bytes() for p in logs)


def test_cli_argument_errors_never_echo_input():
    code = "PRIVATE_ARGUMENT_SENTINEL"
    for arguments in (["serve", "--host", code], ["serve", "--port", code], ["serve", "--" + code]):
        result = subprocess.run([PYTHON, "-m", "nirs4all_repository.project_service", *arguments], capture_output=True)
        assert result.returncode != 0
        assert result.stderr == b"Invalid project service arguments.\n"
        assert code.encode() not in result.stdout + result.stderr


@pytest.mark.parametrize("field,value", [("id", "nl\n"), ("tags", ["x\n"])])
def test_real_http_newline_slug_refused_before_writes(tmp_path, make_catalog, monkeypatch, field, value):
    import yaml

    from nirs4all_repository.project_protocol import SUBMISSION_SCHEMA, digest

    credentials = tmp_path / "credentials.json"
    token, _ = credentials_file(credentials)
    port, process, _, _ = start_server(tmp_path, "CLI", credentials, "PRIVATE_OWNER_SENTINEL")
    monkeypatch.setenv("NIRS4ALL_PROJECT_TOKEN", token)
    bundle = make_catalog() / "pipelines/demo_pipe"
    descriptor = yaml.safe_load((bundle / "descriptor.yaml").read_bytes())
    descriptor[field] = value
    files = {"descriptor.yaml": yaml.safe_dump(descriptor).encode(), "pipeline.json": (bundle / "pipeline.json").read_bytes()}
    body = {"schema": SUBMISSION_SCHEMA, "files": [
        {"relpath": name, "sha256": digest(raw), "content_base64": base64.b64encode(raw).decode()}
        for name, raw in files.items()
    ]}
    try:
        client = ProjectClient("http://127.0.0.1:" + str(port))
        with pytest.raises(ProjectClientError) as error:
            client._request("POST", "/v1/records", body)
        assert error.value.status == 422
        assert error.value.response == {"error": "invalid_descriptor"}
        assert list((tmp_path / "store").iterdir()) == []
    finally:
        stop_server(process)


def test_documented_local_client_exceptions(tmp_path, make_catalog, monkeypatch):
    from nirs4all_repository.project_protocol import content_identity, digest, record_identity

    monkeypatch.setenv("NIRS4ALL_PROJECT_TOKEN", access.generate_token())
    client = ProjectClient("http://127.0.0.1:8123")
    with pytest.raises(FileNotFoundError):
        client.add(tmp_path / "missing-bundle")
    bundle = make_catalog() / "pipelines/demo_pipe"
    descriptor = (bundle / "descriptor.yaml").read_bytes()
    import yaml
    data = yaml.safe_load(descriptor)
    record_id = record_identity(data["id"], data["version"])
    files = {"descriptor.yaml": descriptor, "pipeline.json": (bundle / "pipeline.json").read_bytes()}
    entries = [{"relpath": name, "sha256": digest(raw), "size_bytes": len(raw), "content_base64": base64.b64encode(raw).decode()}
               for name, raw in files.items()]
    monkeypatch.setattr(client, "record", lambda _: {"files": entries, "content_sha256": content_identity(entries)})
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "sentinel"
    sentinel.write_bytes(b"preserve existing contents")
    with pytest.raises(FileExistsError):
        client.materialize(record_id, destination)
    assert sentinel.read_bytes() == b"preserve existing contents"
    assert list(destination.iterdir()) == [sentinel]
    with pytest.raises(FileNotFoundError):
        client.materialize(record_id, tmp_path / "missing-parent" / "destination")


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
@pytest.mark.parametrize("value", ["2026-11-04\n", "2026-11-04", "2026-11-04T12:34:56Z"])
def test_real_http_descriptor_date_fullmatch(tmp_path, make_catalog, monkeypatch, field, value):
    import yaml

    from nirs4all_repository.project_protocol import SUBMISSION_SCHEMA, digest

    credentials = tmp_path / "credentials.json"
    token, _ = credentials_file(credentials)
    port, process, _, _ = start_server(tmp_path, "CLI", credentials, "PRIVATE_OWNER_SENTINEL")
    monkeypatch.setenv("NIRS4ALL_PROJECT_TOKEN", token)
    bundle = make_catalog() / "pipelines/demo_pipe"
    descriptor = yaml.safe_load((bundle / "descriptor.yaml").read_bytes())
    descriptor[field] = value
    raw_descriptor = yaml.safe_dump(descriptor).encode()
    files = {"descriptor.yaml": raw_descriptor, "pipeline.json": (bundle / "pipeline.json").read_bytes()}
    body = {"schema": SUBMISSION_SCHEMA, "files": [
        {"relpath": name, "sha256": digest(raw), "content_base64": base64.b64encode(raw).decode()}
        for name, raw in files.items()
    ]}
    try:
        client = ProjectClient("http://127.0.0.1:" + str(port))
        if value.endswith("\n"):
            with pytest.raises(ProjectClientError) as error:
                client._request("POST", "/v1/records", body)
            assert error.value.status == 422
            assert error.value.response == {"error": "invalid_descriptor"}
            assert list((tmp_path / "store").iterdir()) == []
        else:
            result = client._request("POST", "/v1/records", body)
            assert result["status"] == "created"
            record = client.record(result["record"]["record_id"])
            stored = next(item for item in record["files"] if item["relpath"] == "descriptor.yaml")
            assert base64.b64decode(stored["content_base64"]) == raw_descriptor
            assert yaml.safe_load(raw_descriptor)[field] == value
    finally:
        stop_server(process)
