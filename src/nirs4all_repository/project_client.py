# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Dedicated localhost project client; credentials never come from command lines."""
from __future__ import annotations

import base64
import json
import os
import stat
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .bridge import Pipeline
from .manifest import write_manifests
from .project_protocol import ALLOWED_FILES, HEX, SUBMISSION_SCHEMA, content_identity, digest, record_identity, strict_json
from .project_store import directory, read_file
from .store import load_descriptor_bytes


class ProjectClientError(Exception):
    """A fixed client failure, with an optional structured HTTP refusal."""

    def __init__(self, code: str, *, status: int | None = None, response: dict | None = None):
        super().__init__(code)
        self.status, self.response = status, response


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _token(token_file: Path | None) -> str:
    value = os.environ.get("NIRS4ALL_PROJECT_TOKEN")
    if value is None and token_file is not None:
        try:
            fd = os.open(token_file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            raise ProjectClientError("invalid_token_file") from None
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 1024:
                raise ProjectClientError("invalid_token_file")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                value = stream.read(1025).decode("ascii").strip()
        except (OSError, UnicodeError):
            raise ProjectClientError("invalid_token_file") from None
        finally:
            os.close(fd)
    if not value or len(value) > 1024 or any(c.isspace() or ord(c) < 33 or ord(c) > 126 for c in value):
        raise ProjectClientError("missing_or_invalid_token")
    return value


class ProjectClient:
    """Header-only bearer client with proxies and redirects disabled."""

    def __init__(self, base_url: str, *, token_file: Path | None = None, timeout: float = 35):
        try:
            url = urllib.parse.urlsplit(base_url)
            if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "::1", "localhost"} or url.username is not None
                    or url.password is not None or url.path not in ("", "/") or "?" in base_url or "#" in base_url
                    or any(ord(c) < 33 or ord(c) > 126 for c in base_url) or url.port is None or not 1 <= url.port <= 65535):
                raise ValueError
        except ValueError:
            raise ProjectClientError("invalid_loopback_url") from None
        self._base = base_url.rstrip("/")
        self._credential = _token(token_file)
        self._timeout = timeout
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        try:
            request = urllib.request.Request(self._base + path, data=json.dumps(body).encode() if body is not None else None,
                                             headers={"Authorization": "Bearer " + self._credential, "Content-Type": "application/json"}, method=method)
            with self._opener.open(request, timeout=self._timeout) as response:
                data = strict_json(response.read())
        except urllib.error.HTTPError as exc:
            try:
                refusal = strict_json(exc.read())
                if not isinstance(refusal, dict):
                    refusal = None
            except Exception:
                refusal = None
            raise ProjectClientError("request_refused", status=exc.code, response=refusal) from None
        except Exception:
            raise ProjectClientError("request_failed") from None
        if not isinstance(data, dict):
            raise ProjectClientError("invalid_response")
        return data

    def add(self, bundle_dir: str | Path) -> dict:
        """Send exact descriptor, declared recipe and optional card; never convert."""
        root = Path(bundle_dir).absolute()
        fd = directory(root)
        try:
            raw = read_file(fd, "descriptor.yaml")
            descriptor = load_descriptor_bytes(raw)
            recipe_path = Path(descriptor.recipe.path)
            if recipe_path.is_absolute() or ".." in recipe_path.parts or "\\" in descriptor.recipe.path:
                raise ProjectClientError("invalid_bundle_path")
            # Traverse directories without following symlinks, including refused
            # YAML names: the server must decide the recipe-format refusal.
            recipe_parent = directory(root / recipe_path.parent)
            try:
                recipe = read_file(recipe_parent, recipe_path.name)
            finally:
                os.close(recipe_parent)
            files = {"descriptor.yaml": raw, descriptor.recipe.path: recipe}
            if "card.md" in os.listdir(fd):
                files["card.md"] = read_file(fd, "card.md")
            # Name unsupported entries for an explicit refusal without opening or
            # expanding their payloads. Generated owner manifests are excluded.
            for name in os.listdir(fd):
                if name not in {*files, "manifest.json", "ro-crate-metadata.json"}:
                    files[name] = b""
        finally:
            os.close(fd)
        entries = [{"relpath": n, "sha256": digest(b), "content_base64": base64.b64encode(b).decode("ascii")} for n, b in files.items()]
        return self._request("POST", "/v1/records", {"schema": SUBMISSION_SCHEMA, "files": entries})

    def list(self) -> list[dict]:
        records = self._request("GET", "/v1/records").get("records")
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
            raise ProjectClientError("invalid_response")
        return records

    def record(self, record_id: str) -> dict:
        if not HEX.fullmatch(record_id):
            raise ProjectClientError("invalid_record_id")
        return self._request("GET", "/v1/records/" + record_id)

    def materialize(self, record_id: str, dest: str | Path) -> Pipeline:
        """Verify source digests and construct a Pipeline directly, with no fallback."""
        record = self.record(record_id)
        try:
            entries = record["files"]
            names = [f["relpath"] for f in entries]
            if len(names) != len(set(names)) or set(names) - ALLOWED_FILES or not {"descriptor.yaml", "pipeline.json"} <= set(names):
                raise ValueError
            files = {}
            for entry in entries:
                raw = base64.b64decode(entry["content_base64"], validate=True)
                if digest(raw) != entry["sha256"] or len(raw) != entry["size_bytes"]:
                    raise ValueError
                files[entry["relpath"]] = raw
            descriptor = load_descriptor_bytes(files["descriptor.yaml"])
            if descriptor.recipe.path != "pipeline.json" or record_identity(descriptor.id, descriptor.version) != record_id or content_identity(entries) != record["content_sha256"]:
                raise ValueError
        except Exception:
            raise ProjectClientError("invalid_response") from None
        dest = Path(dest)
        dest.mkdir(mode=0o700, parents=False, exist_ok=False)
        for name, raw in files.items():
            (dest / name).write_bytes(raw)
        write_manifests(dest, descriptor)
        pipeline = Pipeline(descriptor, dest)
        pipeline.verify()
        return pipeline
