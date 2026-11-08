# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Opt-in localhost ASGI service using the independent access verifier.

No request data or exception diagnostics are logged. The CLI deliberately exposes
no transport, logging, proxy, TLS, WebSocket or HTTP-parser overrides.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, NoReturn

from nirs4all_access import AccessError, ProjectTokenVerifier, load_credential_store, parse_bearer, require_secure_transport

from .project_protocol import BODY_LIMIT, Refusal, parse_submission
from .project_store import DISK_FLOOR, ProjectStore


class ProjectService:
    """Authenticate every protected request before receiving its body."""

    def __init__(self, store: ProjectStore, verifier: ProjectTokenVerifier, *, body_deadline: float = 30, max_ingests: int = 4):
        if body_deadline <= 0 or max_ingests < 1:
            raise ValueError("invalid service limits")
        self.store = store
        self.verifier = verifier
        self.body_deadline = body_deadline
        self.ingests = asyncio.Semaphore(max_ingests)

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] == "lifespan":
            while True:
                event = await receive()
                if event["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif event["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            return
        try:
            status, body = await self._http(scope, receive)
            raw = json.dumps(body, separators=(",", ":"), allow_nan=False).encode("utf-8")
        except Refusal as exc:
            status, body = exc.status, exc.body
            raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
        except Exception:
            # Never stringify an exception: an owner failure may contain secrets.
            status, raw = 500, b'{"error":"internal_error"}'
        headers = [(b"content-type", b"application/json"), (b"content-length", str(len(raw)).encode("ascii")),
                   (b"cache-control", b"no-store"), (b"connection", b"close")]
        if status == 401:
            headers.append((b"www-authenticate", b"Bearer"))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": raw})

    async def _http(self, scope: dict, receive: Any) -> tuple[int, dict]:
        method, path = scope["method"], scope["path"]
        if method == "GET" and path == "/healthz" and not scope.get("query_string"):
            return 200, {"status": "ok"}
        record_match = re.fullmatch(r"/v1/records/([0-9a-f]{64})", path)
        right = None
        if path == "/v1/records" and method in ("GET", "POST"):
            right = "repository.read" if method == "GET" else "repository.add"
        elif record_match and method == "GET":
            right = "repository.read"
        headers: dict[bytes, list[bytes]] = {}
        for key, value in scope.get("headers", []):
            headers.setdefault(key.lower(), []).append(value)
        auth = headers.get(b"authorization", [])
        authorization = auth[0].decode("latin-1") if len(auth) == 1 else None
        try:
            principal = self.verifier.verify(parse_bearer(authorization), service="repository", required_rights=[right] if right else [])
        except AccessError as exc:
            body: dict[str, Any] = {"error": exc.code}
            if exc.code == "missing_rights":
                body["missing_rights"] = sorted(exc.missing_rights)
            return exc.status, body
        if right is None:
            raise Refusal(404, "not_found")
        if scope.get("query_string") or any(b"project" in key for key in headers) or b"upgrade" in headers:
            raise Refusal(400, "invalid_request")
        if len(headers.get(b"content-length", [])) > 1 or (b"content-length" in headers and b"transfer-encoding" in headers):
            raise Refusal(400, "invalid_request")
        if b"content-encoding" in headers and headers[b"content-encoding"] != [b"identity"]:
            raise Refusal(415, "unsupported_media_type")
        types = headers.get(b"content-type", [])
        if (method == "POST" and not types) or (types and (len(types) != 1 or types[0].split(b";", 1)[0].strip().lower() != b"application/json")):
            raise Refusal(415, "unsupported_media_type")
        if method == "POST":
            if b"content-length" in headers:
                value = headers[b"content-length"][0]
                if not value.isdigit():
                    raise Refusal(400, "invalid_request")
                if len(value) > 10 or int(value) > BODY_LIMIT:
                    raise Refusal(413, "body_too_large")
            async with self.ingests:
                data = bytearray()
                try:
                    async with asyncio.timeout(self.body_deadline):
                        while True:
                            event = await receive()
                            if event["type"] != "http.request":
                                raise Refusal(400, "invalid_request")
                            chunk = event.get("body", b"")
                            if len(data) + len(chunk) > BODY_LIMIT:
                                raise Refusal(413, "body_too_large")
                            data.extend(chunk)
                            if not event.get("more_body", False):
                                break
                except TimeoutError:
                    raise Refusal(408, "body_timeout") from None
                return await asyncio.to_thread(self._add, principal, bytes(data))
        if record_match:
            return 200, await asyncio.to_thread(self.store.read, principal.project_id, record_match[1], include_files=True)
        return 200, {"records": await asyncio.to_thread(self.store.list, principal.project_id)}

    def _add(self, principal: Any, raw: bytes) -> tuple[int, dict]:
        return self.store.add(principal, parse_submission(raw))


def create_app(store: Path, credentials: Path, *, host: str = "127.0.0.1", disk_floor: int = DISK_FLOOR) -> ProjectService:
    """Freeze a trusted hash-only credential snapshot; revocation needs restart."""
    if os.name != "posix" or host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("localhost POSIX service required")
    require_secure_transport(host, tls=False)
    records = load_credential_store(credentials)
    now = time.time()
    if not any(not r.revoked and (r.expires_at is None or r.expires_at > now) and "repository" in r.principal.services
               and r.principal.rights & {"repository.read", "repository.add"} for r in records):
        raise ValueError("no active repository credential")
    return ProjectService(ProjectStore(store, disk_floor=disk_floor), ProjectTokenVerifier(records))


def serve(app: ProjectService, *, host: str, port: int) -> None:
    """Run the fixed transport profile. No external logging/transport overrides."""
    import uvicorn

    if host not in {"127.0.0.1", "::1", "localhost"} or not 1 <= port <= 65535:
        raise ValueError("invalid loopback address")
    with contextlib.suppress(KeyboardInterrupt):
        uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False, ws="none", http="h11", loop="asyncio",
                    proxy_headers=False, server_header=False, limit_concurrency=32)


class _PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.exit(2, "Invalid project service arguments.\n")


def main() -> None:
    parser = _PrivateArgumentParser(description="Local project-scoped recipe records")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("serve")
    command.add_argument("--store", required=True, type=Path)
    command.add_argument("--credentials", required=True, type=Path)
    command.add_argument("--port", required=True, type=int)
    command.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "::1", "localhost"))
    command.add_argument("--disk-floor", type=int, default=DISK_FLOOR)
    args = parser.parse_args()
    try:
        app = create_app(args.store, args.credentials, host=args.host, disk_floor=args.disk_floor)
        serve(app, host=args.host, port=args.port)
    except Exception:
        # Never print an exception or a configured path (including startup failures).
        parser.exit(1, "Project service failed.\n")


if __name__ == "__main__":
    main()
