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
from dataclasses import dataclass, field
from pathlib import Path

from .recipes import normalize_nirs4all_steps
from .schema import RecipeFormat

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
    try:
        for opcode, arg, _pos in pickletools.genops(io.BytesIO(data)):
            if opcode.name in ("GLOBAL", "STACK_GLOBAL", "INST", "OBJ"):
                module, _, name = _global_target(opcode.name, arg)
                if module in DANGEROUS_PICKLE_MODULES:
                    findings.append(f"pickle imports dangerous module {module!r} ({name})")
                elif (module, name) in DANGEROUS_PICKLE_GLOBALS:
                    findings.append(f"pickle imports dangerous callable {module}.{name}")
                elif module and _module_root(module) not in CURATED_MODULE_ROOTS:
                    findings.append(f"pickle imports non-allowlisted module {module!r}")
    except Exception as exc:  # malformed pickle is itself a finding
        findings.append(f"pickle could not be parsed: {exc}")
    return ScanResult(ok=not findings, findings=findings)


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
    """Scan the raw pickle/joblib file at *path*.

    Note: only uncompressed pickle streams are parseable; compressed or archived blobs
    (e.g. a ``.n4a`` ZIP) must be expanded by the caller before scanning their members.
    """
    return scan_pickle_bytes(path.read_bytes())
