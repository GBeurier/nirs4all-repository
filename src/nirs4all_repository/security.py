# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Security scanning for recipes and fitted artifacts.

See ``SECURITY.md`` for the threat model. Two defences live here:

* :func:`scan_config` — a curated module allow-list for the dotted class references in
  a recipe (blocks config-borne injection).
* :func:`scan_pickle_bytes` — a ``pickletools`` opcode scan flagging dangerous imports
  in a fitted blob. This is a heuristic safety net, **not** a sandbox.

The curated allow-list is authoritative for the publication gate and CI. The
``NIRS4ALL_REPOSITORY_ALLOWLIST`` environment override is a local convenience only and
must be passed in explicitly; it never widens what is published.
"""

from __future__ import annotations

import io
import pickletools
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from .recipes import normalize_nirs4all_steps
from .schema import ArtifactBackend, ArtifactStorage, PipelineDescriptor, RecipeFormat

#: Curated top-level modules whose classes a recipe may reference.
CURATED_MODULE_ROOTS = frozenset(
    {
        "sklearn",
        "scipy",
        "numpy",
        "np",
        "pandas",
        "nirs4all",
        "dag_ml",
        "dag_ml_data",
        "aom_nirs",
        "xgboost",
        "lightgbm",
        "catboost",
    }
)

#: Modules/callables that are never acceptable inside a pickle (code-execution risks).
DANGEROUS_PICKLE_MODULES = frozenset(
    {
        "os",
        "nt",
        "posix",
        "subprocess",
        "sys",
        "socket",
        "shutil",
        "importlib",
        "ctypes",
        "builtins",
        "__builtin__",
        "pty",
        "commands",
        "webbrowser",
        "code",
        "codeop",
        "pickle",
    }
)

#: Specific dangerous callables (module, name) always flagged even if module is allowed.
DANGEROUS_PICKLE_GLOBALS = frozenset(
    {
        ("builtins", "eval"),
        ("builtins", "exec"),
        ("builtins", "compile"),
        ("builtins", "__import__"),
        ("builtins", "getattr"),
        ("builtins", "setattr"),
    }
)

#: File suffixes that are treated as raw, uncompressed pickle streams.
PICKLE_FILE_SUFFIXES = frozenset({".pickle", ".pkl"})

#: Artifact backends whose inline bytes are pickle streams and must be inspected.
PICKLE_STREAM_BACKENDS = frozenset({ArtifactBackend.joblib})

#: Container formats where only explicitly named pickle members are inspected.
PICKLE_ARCHIVE_SUFFIXES = frozenset({".n4a"})

_PICKLE_STRING_OPCODES = frozenset(
    {
        "STRING",
        "BINSTRING",
        "SHORT_BINSTRING",
        "UNICODE",
        "BINUNICODE",
        "BINUNICODE8",
        "SHORT_BINUNICODE",
    }
)

_PICKLE_MEMO_WRITE_OPCODES = frozenset({"BINPUT", "LONG_BINPUT", "PUT"})
_PICKLE_MEMO_READ_OPCODES = frozenset({"BINGET", "LONG_BINGET", "GET"})

_PICKLE_UNKNOWN = object()
_PICKLE_MARK = object()


@dataclass
class ScanResult:
    """Outcome of a security scan."""

    ok: bool
    findings: list[str] = field(default_factory=list)

    def raise_for_findings(self) -> None:
        """Raise :class:`SecurityError` if the scan found anything."""
        if not self.ok:
            raise SecurityError("; ".join(self.findings))


class SecurityError(Exception):
    """Raised when a security scan rejects a recipe or artifact."""


def _module_root(dotted: str) -> str:
    return dotted.split(".", 1)[0]


def _iter_class_refs(recipe_obj: object) -> list[str]:
    """Recursively collect every ``class`` dotted reference in a recipe object."""
    found: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "class" and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str) and "." in node and node.replace(".", "").replace("_", "").isalnum():
            # bare dotted class path as a step
            found.append(node)

    walk(recipe_obj)
    return found


def scan_config(
    recipe: object,
    fmt: RecipeFormat,
    *,
    extra_allowlist: tuple[str, ...] = (),
) -> ScanResult:
    """Scan a recipe's class references against the curated module allow-list.

    Args:
        recipe: the parsed recipe object.
        fmt: the recipe format (only the class-reference shape matters).
        extra_allowlist: additional allowed module roots (local convenience only).

    Returns:
        A :class:`ScanResult`; ``ok`` is ``False`` when any class references a module
        outside the allow-list.
    """
    allowed = CURATED_MODULE_ROOTS | set(extra_allowlist)
    if fmt is RecipeFormat.nirs4all_pipeline_config:
        try:
            scan_target: object = normalize_nirs4all_steps(recipe)
        except Exception:
            scan_target = recipe
    else:
        scan_target = recipe
    findings: list[str] = []
    for ref in _iter_class_refs(scan_target):
        root = _module_root(ref)
        if root not in allowed:
            findings.append(f"class {ref!r} uses non-allowlisted module root {root!r}")
    return ScanResult(ok=not findings, findings=findings)


def scan_pickle_bytes(data: bytes) -> ScanResult:
    """Scan raw pickle *data* for dangerous ``GLOBAL`` imports (heuristic)."""
    findings: list[str] = []
    stack: list[object] = []
    memo: dict[int, object] = {}
    try:
        for opcode, arg, _pos in pickletools.genops(io.BytesIO(data)):
            if opcode.name in _PICKLE_STRING_OPCODES and isinstance(arg, str):
                stack.append(arg)
            elif opcode.name == "GLOBAL":
                module, _, name = _global_target(opcode.name, arg)
                finding = _pickle_global_finding(module, name)
                if finding:
                    findings.append(finding)
                stack.append(_PICKLE_UNKNOWN)
            elif opcode.name == "STACK_GLOBAL":
                name_obj = stack.pop() if stack else _PICKLE_UNKNOWN
                module_obj = stack.pop() if stack else _PICKLE_UNKNOWN
                if isinstance(module_obj, str) and isinstance(name_obj, str):
                    finding = _pickle_global_finding(module_obj, name_obj)
                    if finding:
                        findings.append(finding)
                else:
                    findings.append("pickle uses STACK_GLOBAL with non-literal module/name")
                stack.append(_PICKLE_UNKNOWN)
            elif opcode.name in ("INST", "OBJ"):
                module, _, name = _global_target(opcode.name, arg)
                finding = _pickle_global_finding(module, name)
                if finding:
                    findings.append(finding)
                _apply_pickle_stack_effect(opcode, stack)
            elif opcode.name == "MEMOIZE":
                if stack:
                    memo[len(memo)] = stack[-1]
            elif opcode.name in _PICKLE_MEMO_WRITE_OPCODES:
                if stack:
                    key = _memo_key(arg)
                    if key is not None:
                        memo[key] = stack[-1]
            elif opcode.name in _PICKLE_MEMO_READ_OPCODES:
                key = _memo_key(arg)
                stack.append(memo.get(key, _PICKLE_UNKNOWN) if key is not None else _PICKLE_UNKNOWN)
            else:
                _apply_pickle_stack_effect(opcode, stack)
    except Exception as exc:  # malformed pickle is itself a finding
        findings.append(f"pickle could not be parsed: {exc}")
    deduped = list(dict.fromkeys(findings))
    return ScanResult(ok=not deduped, findings=deduped)


def _pickle_global_finding(module: str, name: str) -> str | None:
    """Return a finding for a pickle global import, or ``None`` when allowed."""
    if not module:
        return None
    root = _module_root(module)
    if module in DANGEROUS_PICKLE_MODULES or root in DANGEROUS_PICKLE_MODULES:
        return f"pickle imports dangerous module {module!r} ({name})"
    if (module, name) in DANGEROUS_PICKLE_GLOBALS:
        return f"pickle imports dangerous callable {module}.{name}"
    if root not in CURATED_MODULE_ROOTS:
        return f"pickle imports non-allowlisted module {module!r}"
    return None


def _memo_key(arg: object) -> int | None:
    if isinstance(arg, int):
        return arg
    if isinstance(arg, str):
        try:
            return int(arg)
        except ValueError:
            return None
    return None


def _apply_pickle_stack_effect(opcode: Any, stack: list[object]) -> None:
    """Apply enough pickle stack semantics to resolve literal ``STACK_GLOBAL`` imports."""
    if opcode.name == "MARK":
        stack.append(_PICKLE_MARK)
        return
    if opcode.name == "POP":
        if stack:
            stack.pop()
        return
    if opcode.name == "POP_MARK":
        _pop_pickle_mark(stack)
        return

    before = getattr(opcode, "stack_before", ())
    after = getattr(opcode, "stack_after", ())
    if any(getattr(item, "name", "") == "stackslice" for item in before):
        _pop_pickle_mark(stack)
    else:
        for _item in before:
            if stack:
                stack.pop()
    for item in after:
        stack.append(_PICKLE_MARK if getattr(item, "name", "") == "mark" else _PICKLE_UNKNOWN)


def _pop_pickle_mark(stack: list[object]) -> None:
    while stack:
        item = stack.pop()
        if item is _PICKLE_MARK:
            break


def _global_target(opcode_name: str, arg: object) -> tuple[str, str, str]:
    """Best-effort (module, sep, name) extraction from a GLOBAL-style opcode arg."""
    if opcode_name == "GLOBAL" and isinstance(arg, str):
        module, _, name = arg.partition(" ")
        return module, " ", name
    # STACK_GLOBAL / INST / OBJ push module+name from the stack; the arg is unavailable
    # here, so we can only flag what GLOBAL gives us. Return empty to skip cleanly.
    if isinstance(arg, str) and " " in arg:
        module, _, name = arg.partition(" ")
        return module, " ", name
    return "", "", ""


def scan_pickle_file(path: Path) -> ScanResult:
    """Scan the raw, uncompressed pickle file at *path*.

    Compressed joblib streams and container formats are not decoded here. Callers that
    handle bundle artifacts should expand supported containers (for example ``.n4a`` ZIP
    files) before scanning pickle members.
    """
    return scan_pickle_bytes(path.read_bytes())


def scan_pickle_archive_members(path: Path) -> ScanResult:
    """Scan ``.pkl``/``.pickle`` members inside a ZIP-format artifact container."""
    findings: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.is_dir() or not _has_pickle_suffix(member.filename):
                    continue
                result = scan_pickle_bytes(archive.read(member))
                findings.extend(_prefix_findings(member.filename, result.findings))
    except zipfile.BadZipFile:
        return ScanResult(ok=True)
    return ScanResult(ok=not findings, findings=findings)


def scan_artifact_pickles(pipeline_path: Path, descriptor: PipelineDescriptor) -> ScanResult:
    """Scan local inline artifact pickles declared by *descriptor*.

    The pass is deliberately scoped to bytes that are part of the bundle: raw
    ``.pkl``/``.pickle`` streams, inline ``joblib`` artifacts, and pickle members inside
    ZIP-format ``.n4a`` artifacts. Remote release artifacts are not fetched here.
    """
    findings: list[str] = []
    for artifact in descriptor.artifacts:
        if artifact.storage is not ArtifactStorage.inline:
            continue
        path = pipeline_path / artifact.relpath
        if not path.is_file():
            continue
        if _should_scan_pickle_stream(path, artifact.backend):
            result = scan_pickle_file(path)
            findings.extend(_prefix_findings(artifact.relpath, result.findings))
        if _should_scan_pickle_archive(path, artifact.backend):
            result = scan_pickle_archive_members(path)
            findings.extend(_prefix_findings(artifact.relpath, result.findings))
    deduped = list(dict.fromkeys(findings))
    return ScanResult(ok=not deduped, findings=deduped)


def scan_pipeline_bundle(
    pipeline_path: Path,
    descriptor: PipelineDescriptor,
    recipe: object,
    *,
    extra_allowlist: tuple[str, ...] = (),
) -> ScanResult:
    """Scan a pipeline recipe plus any local inline pickle artifacts."""
    findings = scan_config(recipe, descriptor.recipe.format, extra_allowlist=extra_allowlist).findings
    findings.extend(scan_artifact_pickles(pipeline_path, descriptor).findings)
    deduped = list(dict.fromkeys(findings))
    return ScanResult(ok=not deduped, findings=deduped)


def _has_pickle_suffix(name: str) -> bool:
    return PurePosixPath(name).suffix.lower() in PICKLE_FILE_SUFFIXES


def _should_scan_pickle_stream(path: Path, backend: ArtifactBackend) -> bool:
    return path.suffix.lower() in PICKLE_FILE_SUFFIXES or backend in PICKLE_STREAM_BACKENDS


def _should_scan_pickle_archive(path: Path, backend: ArtifactBackend) -> bool:
    return path.suffix.lower() in PICKLE_ARCHIVE_SUFFIXES or backend is ArtifactBackend.n4a


def _prefix_findings(context: str, findings: list[str]) -> list[str]:
    return [f"{context}: {finding}" for finding in findings]
