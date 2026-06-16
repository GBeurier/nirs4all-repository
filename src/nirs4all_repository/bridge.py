# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""The :class:`Pipeline` handle returned by ``get`` and the framework bridges.

A :class:`Pipeline` wraps a materialised bundle directory plus its validated
descriptor. The ``to_nirs4all`` / ``to_dagml`` bridges hand the recipe to the target
framework in its native config form; they import the framework lazily and fail with a
clear message if it is absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .manifest import verify_bundle
from .recipes import load_recipe_file, to_canonical_json_recipe
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
        """Return the parsed recipe in its canonical-JSON form."""
        raw = load_recipe_file(self.path / self.descriptor.recipe.path)
        return to_canonical_json_recipe(raw, self.descriptor.recipe.format)

    def to_nirs4all(self) -> Any:
        """Return a nirs4all pipeline config ready for ``nirs4all.run()/predict()``.

        For a recipe pipeline this is the recipe config; for a fitted pipeline the
        caller should instead pass the resolved ``.n4a`` artifact path to
        ``nirs4all.predict(model=...)`` (see :meth:`artifact_path`).
        """
        if self.descriptor.framework is not Framework.nirs4all:
            raise BridgeError(f"pipeline {self.id!r} targets {self.descriptor.framework.value}, not nirs4all")
        return self.recipe()

    def to_dagml(self) -> Any:
        """Return a dag-ml DSL / compiled artifact ready for dag-ml compilation."""
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
