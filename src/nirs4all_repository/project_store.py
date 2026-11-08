# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Immutable project records, staged outside the read namespace and committed once.

The POSIX private store is operator-owned. Reads use directory-relative no-follow
opens throughout; no public catalogue resolver or mutable index is involved.
"""
from __future__ import annotations

import base64
import errno
import os
import shutil
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .manifest import write_manifests
from .project_protocol import CLAIMS, HEX, RECORD_SCHEMA, Refusal, Submission, canonical, content_identity, digest, record_identity, strict_json
from .validate import validate_pipeline

DISK_FLOOR = 2_147_483_648
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


def directory(path: Path, *, create: bool = False) -> int:
    """Open an absolute directory without following any symlink component."""
    path = path.absolute()
    fd = os.open("/", _DIR_FLAGS)
    try:
        for part in path.parts[1:]:
            if part in (".", ".."):
                raise OSError("invalid store")
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
            child = os.open(part, _DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_file(fd: int, name: str) -> bytes:
    handle = os.open(name, _FILE_FLAGS, dir_fd=fd)
    try:
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            raise ValueError("invalid record")
        with os.fdopen(handle, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(handle)


def fsync_tree(path: Path) -> None:
    for root, _dirs, files in os.walk(path, topdown=False):
        for name in files:
            fd = os.open(Path(root) / name, _FILE_FLAGS)
            try:
                os.fchmod(fd, 0o600)
                os.fsync(fd)
            finally:
                os.close(fd)
        fd = directory(Path(root))
        try:
            os.fchmod(fd, 0o700)
            os.fsync(fd)
        finally:
            os.close(fd)


class ProjectStore:
    """A private immutable record store; project IDs come only from the verifier."""

    def __init__(self, root: Path, *, disk_floor: int = DISK_FLOOR):
        if os.name != "posix" or disk_floor < DISK_FLOOR:
            raise ValueError("unsupported store configuration")
        self.root = root.absolute()
        # A catalogue checkout must never be a service store or its ancestor.
        for parent in (self.root, *self.root.parents):
            if (parent / "pipelines").is_dir() and (parent / "catalog").is_dir():
                raise ValueError("store must be outside catalogue checkout")
        fd = directory(self.root, create=True)
        try:
            if os.fstat(fd).st_mode & 0o077:
                raise ValueError("store must be private")
        finally:
            os.close(fd)
        self.disk_floor = disk_floor

    def _project(self, project: str) -> Path:
        # Defense in depth for direct backend use; HTTP supplies only leaf principals.
        if not project or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in project) or len(project) > 63:
            raise ValueError("invalid principal")
        return self.root / "projects" / project

    def read(self, project: str, record_id: str, *, include_files: bool = False) -> dict[str, Any]:
        if not HEX.fullmatch(record_id):
            raise Refusal(404, "not_found")
        base = self._project(project) / "records" / record_id
        try:
            fd = directory(base)
        except FileNotFoundError:
            raise Refusal(404, "not_found") from None
        except OSError:
            raise Refusal(409, "corrupt_record") from None
        try:
            record = strict_json(read_file(fd, "record.json"))
            expected = {"schema", "record_id", "content_sha256", "project_id", "stored_by", "stored_at", "pipeline_id", "pipeline_version", "framework", "kind", "task", "recipe_format", "files", "execution_requirements", *CLAIMS}
            if not isinstance(record, dict) or set(record) != expected:
                raise ValueError
            if any(not isinstance(record[k], str) or not record[k] for k in expected - {"files", "execution_requirements"}):
                raise ValueError
            if not isinstance(record["execution_requirements"], dict) or set(os.listdir(fd)) != {"record.json", "pipelines"}:
                raise ValueError
            if record["schema"] != RECORD_SCHEMA or record["record_id"] != record_id or record["project_id"] != project:
                raise ValueError
            if any(record[k] != v for k, v in CLAIMS.items()) or record["kind"] != "recipe":
                raise ValueError
            pid, version = record["pipeline_id"], record["pipeline_version"]
            if not isinstance(pid, str) or not pid or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in pid):
                raise ValueError
            if record_identity(pid, version) != record_id:
                raise ValueError
            files = record["files"]
            if not isinstance(files, list) or len(files) not in (2, 3):
                raise ValueError
            names = [f["relpath"] for f in files]
            if sorted(names) not in (["descriptor.yaml", "pipeline.json"], ["card.md", "descriptor.yaml", "pipeline.json"]):
                raise ValueError
            if content_identity(files) != record["content_sha256"]:
                raise ValueError
            pipes = os.open("pipelines", _DIR_FLAGS, dir_fd=fd)
            try:
                if os.listdir(pipes) != [pid]:
                    raise ValueError
                bundle = os.open(pid, _DIR_FLAGS, dir_fd=pipes)
            finally:
                os.close(pipes)
            try:
                if set(os.listdir(bundle)) != {*names, "manifest.json", "ro-crate-metadata.json"}:
                    raise ValueError
                returned = []
                for item in files:
                    if set(item) != {"relpath", "sha256", "size_bytes"}:
                        raise ValueError
                    if not isinstance(item["sha256"], str) or HEX.fullmatch(item["sha256"]) is None or type(item["size_bytes"]) is not int or item["size_bytes"] < 0:
                        raise ValueError
                    raw = read_file(bundle, item["relpath"])
                    if digest(raw) != item["sha256"] or len(raw) != item["size_bytes"]:
                        raise ValueError
                    returned.append({**item, "content_base64": base64.b64encode(raw).decode("ascii")})
                manifest = strict_json(read_file(bundle, "manifest.json"))
                crate = strict_json(read_file(bundle, "ro-crate-metadata.json"))
                if manifest["files"] != files or manifest["id"] != pid or manifest["pipeline_version"] != version or manifest["execution_requirements"] != record["execution_requirements"]:
                    raise ValueError
                crate_files = {x["@id"]: x["sha256"] for x in crate["@graph"] if x.get("@type") == "File"}
                if crate_files != {f["relpath"]: f["sha256"] for f in files}:
                    raise ValueError
                if include_files:
                    record = {**record, "files": returned}
                return record
            finally:
                os.close(bundle)
        except Exception:
            raise Refusal(409, "corrupt_record") from None
        finally:
            os.close(fd)

    def list(self, project: str) -> list[dict]:
        try:
            fd = directory(self._project(project) / "records")
        except FileNotFoundError:
            return []
        except OSError:
            raise Refusal(409, "corrupt_project") from None
        try:
            names = sorted(n for n in os.listdir(fd) if HEX.fullmatch(n))
        finally:
            os.close(fd)
        records = []
        for name in names:
            try:
                records.append(self.read(project, name))
            except Refusal:
                records.append({"record_id": name, "error": "corrupt_record"})
        return records

    def _existing(self, project: str, submission: Submission) -> dict | None:
        try:
            record = self.read(project, submission.record_id)
        except Refusal as exc:
            if exc.status == 404:
                return None
            raise
        if record["content_sha256"] != submission.content_sha256:
            raise Refusal(409, "pipeline_version_conflict")
        return record

    def add(self, principal: Any, submission: Submission) -> tuple[int, dict]:
        project = principal.project_id
        existing = self._existing(project, submission)
        if existing is not None:
            return 200, {"status": "already_present", "record": existing}
        if shutil.disk_usage(self.root).free < self.disk_floor:
            raise Refusal(507, "insufficient_storage")
        project_root = self._project(project)
        stage = None
        try:
            for child in ("staging", "records"):
                fd = directory(project_root / child, create=True)
                os.close(fd)
            stage = Path(tempfile.mkdtemp(dir=project_root / "staging"))
            descriptor = submission.descriptor
            bundle = stage / "pipelines" / descriptor.id
            bundle.mkdir(parents=True, mode=0o700)
            for name, data in submission.files.items():
                (bundle / name).write_bytes(data)
            report = validate_pipeline(stage, descriptor.id, strict=False, extra_allowlist=())
            if report.security_findings:
                raise Refusal(422, "security_refused")
            if report.errors:
                raise Refusal(422, "recipe_structure_invalid")
            write_manifests(bundle, descriptor)
            for name, data in submission.files.items():
                if digest((bundle / name).read_bytes()) != digest(data):
                    raise Refusal(422, "digest_mismatch")
            manifest = strict_json((bundle / "manifest.json").read_bytes())
            record = {
                "schema": RECORD_SCHEMA, "record_id": submission.record_id,
                "content_sha256": submission.content_sha256, "project_id": project,
                "stored_by": principal.principal_id, "stored_at": datetime.now(UTC).isoformat(),
                "pipeline_id": descriptor.id, "pipeline_version": descriptor.version,
                "framework": descriptor.framework.value, "kind": descriptor.kind.value,
                "task": descriptor.task.value, "recipe_format": descriptor.recipe.format.value,
                "files": submission.file_records, "execution_requirements": manifest["execution_requirements"], **CLAIMS,
            }
            (stage / "record.json").write_bytes(canonical(record) + b"\n")
            fsync_tree(stage)
            records_fd = directory(project_root / "records")
            staging_fd = directory(project_root / "staging")
            try:
                try:
                    os.rename(stage.name, submission.record_id, src_dir_fd=staging_fd, dst_dir_fd=records_fd)
                except OSError as exc:
                    if exc.errno not in (errno.EEXIST, errno.ENOTEMPTY):
                        raise
                    winner = self._existing(project, submission)
                    if winner is None:
                        raise Refusal(409, "corrupt_record") from None
                    return 200, {"status": "already_present", "record": winner}
                os.fsync(records_fd)
                os.fsync(staging_fd)
            finally:
                os.close(records_fd)
                os.close(staging_fd)
            return 201, {"status": "created", "record": record}
        except OSError as exc:
            if exc.errno in (errno.ENOSPC, errno.EDQUOT):
                raise Refusal(507, "insufficient_storage") from None
            raise
        finally:
            if stage is not None and stage.exists():
                shutil.rmtree(stage)
