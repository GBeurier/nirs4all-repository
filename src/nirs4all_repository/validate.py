# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Static (hermetic) validation of catalogue pipelines.

This is the CI gate: no network, no heavy framework imports. It checks descriptor
schema validity, recipe structure, bundle checksums, and the security scan, and reports
publication readiness. Strict framework-level recipe validation is opt-in and imported
lazily.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .manifest import verify_bundle
from .recipes import RecipeError, load_recipe_file, validate_recipe_structure
from .schema import PipelineDescriptor
from .security import scan_config
from .store import (
    DESCRIPTOR_FILENAME,
    list_pipeline_ids,
    load_descriptor_file,
    pipeline_dir,
)


@dataclass
class ValidationReport:
    """The outcome of validating a single pipeline."""

    pipeline_id: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    security_findings: list[str] = field(default_factory=list)
    publication_blockers: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """``True`` when there are no errors or security findings."""
        return not self.errors and not self.security_findings


def validate_pipeline(
    root: Path,
    pipeline_id: str,
    *,
    strict: bool = False,
    extra_allowlist: tuple[str, ...] = (),
) -> ValidationReport:
    """Statically validate one pipeline bundle and return a :class:`ValidationReport`."""
    report = ValidationReport(pipeline_id=pipeline_id)
    path = pipeline_dir(root, pipeline_id)
    descriptor_path = path / DESCRIPTOR_FILENAME

    if not descriptor_path.is_file():
        report.errors.append(f"missing {DESCRIPTOR_FILENAME}")
        return report

    try:
        descriptor: PipelineDescriptor = load_descriptor_file(descriptor_path)
    except Exception as exc:
        report.errors.append(f"descriptor invalid: {exc}")
        return report

    if descriptor.id != pipeline_id:
        report.errors.append(f"descriptor id {descriptor.id!r} != directory name {pipeline_id!r}")

    recipe_path = path / descriptor.recipe.path
    if not recipe_path.is_file():
        report.errors.append(f"recipe file missing: {descriptor.recipe.path}")
        return report

    try:
        recipe = load_recipe_file(recipe_path)
    except Exception as exc:
        report.errors.append(f"recipe could not be parsed: {exc}")
        return report

    try:
        validate_recipe_structure(recipe, descriptor.recipe.format)
    except RecipeError as exc:
        report.errors.append(f"recipe structure invalid: {exc}")

    scan = scan_config(recipe, descriptor.recipe.format, extra_allowlist=extra_allowlist)
    report.security_findings.extend(scan.findings)

    report.errors.extend(verify_bundle(path, descriptor))

    if strict:
        report.warnings.extend(_strict_check(recipe, descriptor))

    report.publication_blockers = descriptor.publication_blockers()
    return report


def _strict_check(recipe: object, descriptor: PipelineDescriptor) -> list[str]:
    """Opt-in framework-level recipe validation; returns warnings (never hard errors)."""
    from .schema import Framework

    warnings: list[str] = []
    if descriptor.framework is Framework.nirs4all:
        try:
            from nirs4all.pipeline.config.pipeline_config import PipelineConfigs
        except Exception:
            warnings.append("strict nirs4all check skipped: nirs4all not installed")
            return warnings
        try:
            PipelineConfigs(recipe)
        except Exception as exc:  # pragma: no cover - depends on optional dep
            warnings.append(f"nirs4all rejected the recipe: {exc}")
    return warnings


def validate_all(root: Path, *, strict: bool = False, extra_allowlist: tuple[str, ...] = ()) -> list[ValidationReport]:
    """Validate every pipeline in the catalogue at *root*."""
    return [validate_pipeline(root, pid, strict=strict, extra_allowlist=extra_allowlist) for pid in list_pipeline_ids(root)]
