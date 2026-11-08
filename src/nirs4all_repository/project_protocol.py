# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Closed project submission protocol. No execution or source conversion."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from .recipes import load_recipe_text
from .schema import PipelineDescriptor
from .store import load_descriptor_bytes

SUBMISSION_SCHEMA = "nirs4all-repository/project-submission/v1"
RECORD_SCHEMA = "nirs4all-repository/project-record/v1"
BODY_LIMIT = 1 << 20
FILE_LIMIT = 512 << 10
ALLOWED_FILES = frozenset({"descriptor.yaml", "pipeline.json", "card.md"})
HEX = re.compile(r"[0-9a-f]{64}")
VERSION = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_-]{0,63}")
CLAIMS = {
    "scope": "project",
    "provenance_status": "asserted_unverified",
    "rights_status": "asserted_unverified",
    "static_validation": "passed_at_ingest",
    "functional_validation": "not_run",
    "execution_status": "not_executed",
    "publication_status": "not_published",
}


class Refusal(Exception):
    """Fixed HTTP refusal; never contains owner diagnostics or request data."""

    def __init__(self, status: int, code: str):
        self.status = status
        self.body: dict[str, Any] = {"error": code}
        if code == "recipe_format_unsupported":
            self.body.update(accepted_recipe_files=["pipeline.json"], conversion="not_performed")
        super().__init__(code)


def canonical(value: Any) -> bytes:
    """Canonical UTF-8 JSON used for record identity and private metadata."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def record_identity(pipeline_id: str, version: str) -> str:
    return digest((RECORD_SCHEMA + "\0" + pipeline_id + "\0" + version).encode("utf-8"))


def content_identity(files: list[dict]) -> str:
    return digest(canonical(sorted((f["relpath"], f["sha256"]) for f in files)))


def strict_json(raw: bytes) -> Any:
    # Reuse the owner parser, including duplicate keys and nonfinite rejection.
    return load_recipe_text(raw.decode("utf-8", errors="strict"), filename="pipeline.json")


@dataclass(frozen=True)
class Submission:
    descriptor: PipelineDescriptor
    files: dict[str, bytes]
    file_records: list[dict]
    record_id: str
    content_sha256: str


def parse_submission(raw: bytes) -> Submission:
    """Apply R2's evaluation order before creating any staging directory."""
    try:
        body = strict_json(raw)
        if not isinstance(body, dict) or set(body) != {"schema", "files"} or body["schema"] != SUBMISSION_SCHEMA:
            raise ValueError
        entries = body["files"]
        if not isinstance(entries, list) or not entries:
            raise ValueError
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"relpath", "sha256", "content_base64"}:
                raise ValueError
            if any(not isinstance(entry[k], str) for k in entry):
                raise ValueError
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise Refusal(400, "invalid_request") from None
    names = [e["relpath"] for e in entries]
    if any(n != "descriptor.yaml" and n.lower().endswith((".yaml", ".yml")) for n in names):
        raise Refusal(422, "recipe_format_unsupported")
    if any(n.lower().endswith(".n4a") for n in names):
        raise Refusal(422, "fitted_unsupported")
    if any(n not in ALLOWED_FILES for n in names) or len(set(names)) != len(names) or not {"descriptor.yaml", "pipeline.json"} <= set(names):
        raise Refusal(422, "undeclared_file")
    files = {}
    for entry in entries:
        try:
            data = base64.b64decode(entry["content_base64"], validate=True)
            if not HEX.fullmatch(entry["sha256"]) or digest(data) != entry["sha256"]:
                raise ValueError
        except (ValueError, binascii.Error):
            raise Refusal(422, "digest_mismatch") from None
        if len(data) > FILE_LIMIT:
            raise Refusal(413, "file_too_large")
        files[entry["relpath"]] = data
    try:
        descriptor = load_descriptor_bytes(files["descriptor.yaml"])
        if len(descriptor.id) > 128 or not VERSION.fullmatch(descriptor.version):
            raise ValueError
    except Exception:
        raise Refusal(422, "invalid_descriptor") from None
    if descriptor.recipe.path != "pipeline.json":
        raise Refusal(422, "recipe_format_unsupported")
    if (
        descriptor.governance.status.value != "draft"
        or descriptor.governance.trust.value == "official"
        or (descriptor.evaluation is not None and (descriptor.evaluation.status.value != "unvalidated" or descriptor.evaluation.validated_at is not None))
        or (descriptor.provenance is not None and descriptor.provenance.fingerprints)
    ):
        raise Refusal(422, "server_owned_field")
    if descriptor.kind.value == "fitted" or descriptor.artifacts:
        raise Refusal(422, "fitted_unsupported")
    try:
        recipe = strict_json(files["pipeline.json"])
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise Refusal(422, "recipe_not_strict_json") from None
    stack = [(recipe, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if depth > 64 or nodes > 100_000:
            raise Refusal(422, "recipe_limits_exceeded")
        if isinstance(item, str):
            try:
                item.encode("utf-8", errors="strict")
            except UnicodeError:
                raise Refusal(422, "recipe_not_strict_json") from None
        elif isinstance(item, dict):
            stack.extend((x, depth + 1) for pair in item.items() for x in pair)
        elif isinstance(item, list):
            stack.extend((x, depth + 1) for x in item)
    records = sorted(({"relpath": n, "sha256": digest(b), "size_bytes": len(b)} for n, b in files.items()), key=lambda f: f["relpath"])
    return Submission(descriptor, files, records, record_identity(descriptor.id, descriptor.version), content_identity(records))
