#!/usr/bin/env python3
"""Validate the Repository V1 surface and probe exact nirs4all train sources."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "public-v1-surface.n4a.json"
SCHEMA_VERSION = "n4a.repository-public-v1-surface/v1"


class SurfaceContractError(RuntimeError):
    """Raised when the declared Repository surface does not match the code."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SurfaceContractError(message)


def _load_contract() -> dict[str, Any]:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    _require(data.get("schema_version") == SCHEMA_VERSION, "unsupported contract schema")
    _require(data.get("surface_id") == "nirs4all.repository.catalog", "unexpected surface id")
    _require(data.get("release_train") == "native-v1-r1-r4", "unexpected release train")
    return data


def _load_repository_package() -> Any:
    source = str(ROOT / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    import nirs4all_repository

    return nirs4all_repository


def validate_repository_surface(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate the declared package API, dependency window, and recipe set."""
    package = _load_repository_package()
    distribution = contract["distribution"]
    _require(package.__version__ == distribution["version"], "package version differs from contract")
    _require(package.__all__ == contract["public_exports"], "public exports differ from contract")

    actual_signatures = {name: str(inspect.signature(getattr(package, name))) for name in contract["callable_signatures"]}
    _require(actual_signatures == contract["callable_signatures"], "callable signatures differ from contract")
    for name in contract["provider_entry_points"]:
        _require(name in package.__all__ and callable(getattr(package, name)), f"missing provider entry point: {name}")

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirement = project["optional-dependencies"]["nirs4all"]
    _require(requirement == [contract["nirs4all_integration"]["extra_requirement"]], "nirs4all extra differs from contract")

    recipe_ids = [entry["id"] for entry in package.list(root=ROOT, framework="nirs4all")]
    _require(recipe_ids == contract["nirs4all_integration"]["recipe_ids"], "nirs4all recipe set differs from contract")
    for pipeline_id in recipe_ids:
        pipeline = package.get_pipeline(pipeline_id, root=ROOT)
        _require(package.get_bundle(pipeline_id, root=ROOT) == pipeline.path, f"bundle mismatch: {pipeline_id}")
        _require(isinstance(pipeline.to_nirs4all(), dict), f"recipe is not a mapping: {pipeline_id}")

    return {
        "distribution": distribution,
        "public_exports": contract["public_exports"],
        "provider_entry_points": contract["provider_entry_points"],
        "recipe_ids": recipe_ids,
    }


def _git(source: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(source), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def probe_source(contract: dict[str, Any], milestone: str, source: Path) -> dict[str, Any]:
    """Probe all Repository recipes against one exact nirs4all source checkout."""
    expected = contract["nirs4all_integration"]["milestones"].get(milestone)
    _require(expected is not None, f"unknown milestone: {milestone}")
    source = source.resolve()
    _require(source.is_dir(), f"source checkout does not exist: {source}")
    _require(_git(source, "rev-parse", "HEAD") == expected["head"], f"{milestone}: source HEAD differs from contract")
    _require(_git(source, "rev-parse", "HEAD^{tree}") == expected["tree"], f"{milestone}: source tree differs from contract")

    sys.path.insert(0, str(source))
    import nirs4all

    package_path = Path(nirs4all.__file__).resolve()
    _require(package_path.is_relative_to(source), f"{milestone}: nirs4all did not import from the requested source")
    _require(nirs4all.__version__ == expected["version"], f"{milestone}: imported version differs from contract")
    _require(hasattr(nirs4all, "PipelineConfigs"), f"{milestone}: public PipelineConfigs export is missing")

    repository = _load_repository_package()
    loaded: list[str] = []
    for pipeline_id in contract["nirs4all_integration"]["recipe_ids"]:
        recipe = repository.get_pipeline(pipeline_id, root=ROOT).to_nirs4all()
        nirs4all.PipelineConfigs(recipe)
        loaded.append(pipeline_id)

    return {
        "milestone": milestone,
        "version": nirs4all.__version__,
        "head": expected["head"],
        "tree": expected["tree"],
        "source": str(source),
        "recipes_loaded": loaded,
        "status": "passed",
    }


def _parse_source(value: str) -> tuple[str, Path]:
    milestone, separator, path = value.partition("=")
    if not separator or not milestone or not path:
        raise argparse.ArgumentTypeError("source must be MILESTONE=PATH")
    return milestone, Path(path)


def _run_isolated_probe(milestone: str, source: Path) -> dict[str, Any]:
    command = [sys.executable, str(Path(__file__).resolve()), "--probe", milestone, str(source)]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(source.resolve()), str(ROOT / "src")))
    result = subprocess.run(command, check=False, capture_output=True, text=True, env=env)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise SurfaceContractError(f"{milestone} probe failed: {detail}")
    return json.loads(result.stdout)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        action="append",
        type=_parse_source,
        default=[],
        metavar="MILESTONE=PATH",
        help="Probe an exact nirs4all source checkout; repeat for R1, R2, and R3.",
    )
    parser.add_argument(
        "--surface-only",
        action="store_true",
        help="Validate the Repository package surface without claiming train compatibility.",
    )
    parser.add_argument("--probe", nargs=2, metavar=("MILESTONE", "PATH"), help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        contract = _load_contract()
        if args.probe:
            print(json.dumps(probe_source(contract, args.probe[0], Path(args.probe[1])), sort_keys=True))
            return 0

        surface = validate_repository_surface(contract)
        requested = [milestone for milestone, _ in args.source]
        _require(len(requested) == len(set(requested)), "each milestone may be probed only once")
        expected = list(contract["nirs4all_integration"]["milestones"])
        if args.surface_only:
            _require(not requested, "--surface-only cannot be combined with --source")
        else:
            _require(requested == expected, f"full train probe order must be {expected}")
        probes = [_run_isolated_probe(milestone, source) for milestone, source in args.source]
        report = {
            "schema_version": SCHEMA_VERSION,
            "surface_id": contract["surface_id"],
            "release_train": contract["release_train"],
            "contract_sha256": hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
            "surface": surface,
            "milestones": probes,
            "status": "passed",
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError, SurfaceContractError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
