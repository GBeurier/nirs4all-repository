# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""The :class:`Pipeline` handle returned by ``get`` and the framework bridges.

A :class:`Pipeline` wraps a materialised bundle directory plus its validated
descriptor. The ``to_nirs4all`` / ``to_dagml`` bridges hand the recipe to the target
framework as parsed data. These bridges do not compile, lower or qualify execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .manifest import verify_bundle
from .recipes import execution_requirements, load_recipe_file, validate_recipe_structure
from .schema import Framework, Kind, PipelineDescriptor


class BridgeError(Exception):
    """Raised when a recipe cannot be bridged to the requested framework."""


@dataclass(frozen=True)
class Pipeline:
    """A resolved catalogue pipeline: its descriptor and on-disk bundle.

    Attributes:
        descriptor: the validated :class:`PipelineDescriptor`.
        path: the bundle directory (a checkout, the bundled copy, or a cache entry).
    """

    descriptor: PipelineDescriptor
    path: Path

    @property
    def id(self) -> str:
        """The pipeline id."""
        return self.descriptor.id

    def recipe(self) -> Any:
        """Return the exact parsed recipe tree, rejecting ambiguous/invalid inputs."""
        raw = load_recipe_file(self.path / self.descriptor.recipe.path)
        validate_recipe_structure(raw, self.descriptor.recipe.format)
        return raw

    def execution_requirements(self) -> dict[str, Any]:
        """Return derived observations with unproven execution dimensions unknown.

        Recompute from the descriptor and recipe, including remote bundles which do
        not carry a manifest. This does not assert runtime support.
        """
        return execution_requirements(self.recipe(), self.descriptor.framework, self.descriptor.recipe.format)

    def to_nirs4all(self) -> Any:
        """Return a nirs4all config or refuse root fields known to be discarded.

        For a recipe pipeline this is the recipe config; for a fitted pipeline the
        caller should instead pass the resolved ``.n4a`` artifact path to
        ``nirs4all.predict(model=...)`` (see :meth:`artifact_path`).
        """
        if self.descriptor.framework is not Framework.nirs4all:
            raise BridgeError(f"pipeline {self.id!r} targets {self.descriptor.framework.value}, not nirs4all")
        recipe = self.recipe()
        if isinstance(recipe, dict):
            unknown = set(recipe) - {"pipeline", "steps", "random_state", "name", "description"}
            if unknown:
                raise BridgeError(f"refusing nirs4all export: root fields would be lost: {sorted(unknown)}; use recipe() for exact content")
        return recipe

    def to_dagml(self) -> Any:
        """Return the exact dag-ml tree; compilation remains the owner's decision."""
        if self.descriptor.framework is not Framework.dag_ml:
            raise BridgeError(f"pipeline {self.id!r} targets {self.descriptor.framework.value}, not dag-ml")
        return self.recipe()

    def artifact_path(self, name: str | None = None) -> Path:
        """Return the local path of a fitted artifact blob (by *name*, or the first)."""
        if self.descriptor.kind is not Kind.fitted:
            raise BridgeError(f"pipeline {self.id!r} is a recipe and has no artifacts")
        for artifact in self.descriptor.artifacts:
            if name is None or artifact.name == name:
                return self.path / artifact.relpath
        raise BridgeError(f"artifact {name!r} not found in pipeline {self.id!r}")

    def verify(self) -> None:
        """Recompute every data-file SHA-256 and raise on any mismatch."""
        problems = verify_bundle(self.path, self.descriptor)
        if problems:
            raise BridgeError(f"bundle verification failed for {self.id!r}: " + "; ".join(problems))
