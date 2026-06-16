# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Pydantic models for the pipeline descriptor and its parts.

``PipelineDescriptor`` is the schema-validated unit of catalogue membership, authored
as ``pipelines/<id>/descriptor.yaml``. All models are versioned by ``schema_version``;
:data:`SCHEMA_VERSION` / :data:`MIN_READABLE` / :data:`MIN_WRITABLE` form the
dag-ml-style compatibility window enforced by :func:`check_schema_version`.

See ``docs/SPECIFICATION.md`` for the authoritative field reference.
"""

from __future__ import annotations

import datetime as _dt
import re
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .canonical import is_safe_relpath, is_sha256, is_slug

#: Current descriptor/index schema version emitted by writers.
SCHEMA_VERSION = 1
#: Oldest schema version a reader will accept.
MIN_READABLE = 1
#: Oldest schema version a writer will (re-)emit.
MIN_WRITABLE = 1

#: SPDX license tokens considered "open" for the publication gate.
_OPEN_LICENSE_TOKENS = (
    "cecill",
    "agpl",
    "gpl",
    "lgpl",
    "mpl",
    "apache",
    "bsd",
    "mit",
    "cc-by",
    "cc0",
    "isc",
    "unlicense",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ].*)?$")


class SchemaVersionError(ValueError):
    """Raised when an artifact's ``schema_version`` is outside the supported window."""


def check_schema_version(version: int, *, what: str = "artifact") -> None:
    """Raise :class:`SchemaVersionError` if *version* cannot be read by this package."""
    if version < MIN_READABLE:
        raise SchemaVersionError(
            f"{what} schema_version {version} is below the minimum readable version {MIN_READABLE}"
        )
    if version > SCHEMA_VERSION:
        raise SchemaVersionError(
            f"{what} schema_version {version} is newer than this package supports "
            f"(max {SCHEMA_VERSION}); upgrade nirs4all-repository"
        )


class Framework(StrEnum):
    """The framework a recipe targets."""

    nirs4all = "nirs4all"
    dag_ml = "dag-ml"


class Kind(StrEnum):
    """Whether the pipeline ships fitted artifacts."""

    recipe = "recipe"
    fitted = "fitted"


class Task(StrEnum):
    """The learning task the pipeline addresses."""

    regression = "regression"
    classification = "classification"
    multitask = "multitask"
    clustering = "clustering"
    other = "other"


class RecipeFormat(StrEnum):
    """The concrete recipe serialisation (see ``SPECIFICATION.md`` §6)."""

    nirs4all_pipeline_config = "nirs4all/pipeline-config"
    dagml_pipeline_dsl = "dag-ml/pipeline-dsl"
    dagml_compiled_artifact = "dag-ml/compiled-artifact"


class ArtifactBackend(StrEnum):
    """The serialisation backend of a fitted artifact blob."""

    n4a = "n4a"
    joblib = "joblib"
    onnx = "onnx"
    safetensors = "safetensors"
    json = "json"
    raw = "raw"


class ArtifactStorage(StrEnum):
    """Where an artifact blob's bytes live."""

    inline = "inline"
    release = "release"


class ReferenceSource(StrEnum):
    """How the reference dataset is located."""

    nirs4all_datasets = "nirs4all-datasets"
    doi = "doi"
    url = "url"


class GovernanceStatus(StrEnum):
    """Catalogue lifecycle state of the pipeline."""

    draft = "draft"
    published = "published"
    deprecated = "deprecated"


class Visibility(StrEnum):
    """Audience of the pipeline (only ``public`` is supported in 0.1.0)."""

    public = "public"


class Trust(StrEnum):
    """Provenance/trust tier of the pipeline."""

    official = "official"
    community = "community"
    experimental = "experimental"


class EvaluationStatus(StrEnum):
    """Outcome of functional evaluation against the reference dataset."""

    unvalidated = "unvalidated"
    validated = "validated"
    failed = "failed"


def _validate_date(value: str | None) -> str | None:
    if value is None:
        return None
    if not _DATE_RE.match(value):
        raise ValueError(f"expected an ISO date (YYYY-MM-DD), got {value!r}")
    return value


class Author(BaseModel):
    """A pipeline author / contributor."""

    model_config = ConfigDict(extra="forbid")

    name: str
    email: str | None = None
    orcid: str | None = None
    affiliation: str | None = None


class Recipe(BaseModel):
    """Pointer to the recipe file inside the bundle."""

    model_config = ConfigDict(extra="forbid")

    format: RecipeFormat
    path: str

    @field_validator("path")
    @classmethod
    def _safe_path(cls, value: str) -> str:
        if not is_safe_relpath(value):
            raise ValueError(f"recipe.path must be a safe relative path, got {value!r}")
        return value


class Artifact(BaseModel):
    """A fitted artifact blob (maps 1:1 to dag-ml ``ArtifactRef``)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    backend: ArtifactBackend
    relpath: str
    sha256: str
    size_bytes: int = Field(ge=0)
    storage: ArtifactStorage = ArtifactStorage.inline
    download_url: str | None = None

    @field_validator("relpath")
    @classmethod
    def _safe_relpath(cls, value: str) -> str:
        if not is_safe_relpath(value):
            raise ValueError(f"artifact.relpath must be a safe relative path, got {value!r}")
        return value

    @field_validator("sha256")
    @classmethod
    def _hex_digest(cls, value: str) -> str:
        if not is_sha256(value):
            raise ValueError(f"artifact.sha256 must be a 64-hex digest, got {value!r}")
        return value

    @model_validator(mode="after")
    def _release_needs_url(self) -> Artifact:
        if self.storage is ArtifactStorage.release and not self.download_url:
            raise ValueError(f"artifact {self.name!r} has storage=release but no download_url")
        return self


class Reference(BaseModel):
    """The reference dataset a pipeline is evaluated against."""

    model_config = ConfigDict(extra="forbid")

    source: ReferenceSource
    name: str | None = None
    doi: str | None = None
    split: str | None = None

    @model_validator(mode="after")
    def _locator_present(self) -> Reference:
        if self.source is ReferenceSource.nirs4all_datasets and not self.name:
            raise ValueError("reference.source=nirs4all-datasets requires a dataset name")
        if self.source is ReferenceSource.doi and not self.doi:
            raise ValueError("reference.source=doi requires a doi")
        if self.source is ReferenceSource.url and not self.name:
            raise ValueError("reference.source=url requires the url in reference.name")
        return self


class ExpectedMetric(BaseModel):
    """An expected metric value with tolerance for a partition."""

    model_config = ConfigDict(extra="forbid")

    value: float
    tol: float = Field(ge=0.0)


class Evaluation(BaseModel):
    """Expected metrics and the recorded functional-validation outcome."""

    model_config = ConfigDict(extra="forbid")

    metric: str
    task: Task | None = None
    expected: dict[str, ExpectedMetric] = Field(default_factory=dict)
    nirs4all_version: str | None = None
    status: EvaluationStatus = EvaluationStatus.unvalidated
    validated_at: str | None = None

    _check_validated_at = field_validator("validated_at")(_validate_date)


class Provenance(BaseModel):
    """Origin and identity fingerprints of the recipe/artifacts."""

    model_config = ConfigDict(extra="forbid")

    generated_by: str | None = None
    fingerprints: dict[str, str] = Field(default_factory=dict)
    source: str | None = None
    notes: str | None = None


class Governance(BaseModel):
    """Catalogue lifecycle, visibility, and trust tier."""

    model_config = ConfigDict(extra="forbid")

    status: GovernanceStatus = GovernanceStatus.draft
    visibility: Visibility = Visibility.public
    trust: Trust = Trust.community


class PipelineDescriptor(BaseModel):
    """The schema-validated descriptor of a single catalogue pipeline."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    id: str
    name: str
    summary: Annotated[str, Field(max_length=200)]
    description: str | None = None
    framework: Framework
    kind: Kind
    task: Task = Task.other
    tags: list[str] = Field(default_factory=list)
    version: str
    license: str
    created_at: str
    updated_at: str | None = None
    authors: list[Author] = Field(min_length=1)
    recipe: Recipe
    artifacts: list[Artifact] = Field(default_factory=list)
    reference: Reference | None = None
    evaluation: Evaluation | None = None
    provenance: Provenance | None = None
    governance: Governance = Field(default_factory=Governance)

    @field_validator("schema_version")
    @classmethod
    def _supported_schema(cls, value: int) -> int:
        check_schema_version(value, what="descriptor")
        return value

    @field_validator("id")
    @classmethod
    def _valid_slug(cls, value: str) -> str:
        if not is_slug(value):
            raise ValueError(f"id must be a slug ^[a-z0-9]+(?:_[a-z0-9]+)*$, got {value!r}")
        return value

    @field_validator("created_at")
    @classmethod
    def _created_date(cls, value: str) -> str:
        result = _validate_date(value)
        assert result is not None
        return result

    _check_updated_at = field_validator("updated_at")(_validate_date)

    @field_validator("tags")
    @classmethod
    def _slug_tags(cls, value: list[str]) -> list[str]:
        for tag in value:
            if not is_slug(tag):
                raise ValueError(f"tag must be a slug, got {tag!r}")
        return value

    @model_validator(mode="after")
    def _kind_artifacts_consistency(self) -> PipelineDescriptor:
        if self.kind is Kind.fitted and not self.artifacts:
            raise ValueError("kind=fitted requires at least one artifact")
        if self.kind is Kind.recipe and self.artifacts:
            raise ValueError("kind=recipe must not declare artifacts")
        if self.evaluation is not None and self.reference is None:
            raise ValueError("evaluation requires a reference dataset")
        return self

    # -- derived helpers -------------------------------------------------------

    def is_open_license(self) -> bool:
        """Return ``True`` if the declared license is an open-source/open-content one."""
        low = self.license.lower()
        return any(token in low for token in _OPEN_LICENSE_TOKENS)

    def publication_blockers(self) -> list[str]:
        """Return the reasons this pipeline may **not** be published (empty == ready).

        A pipeline may be ``governance.status: published`` only when this list is empty.
        Open license + an author + provenance + (assumed) passing static validation are
        always required; ``official``/``community`` trust additionally require functional
        validation (``evaluation.status == validated``).
        """
        blockers: list[str] = []
        if not self.is_open_license():
            blockers.append(f"license {self.license!r} is not an open license")
        if not self.authors:
            blockers.append("at least one author is required")
        if self.provenance is None:
            blockers.append("provenance is required for publication")
        if self.governance.trust in (Trust.official, Trust.community) and (
            self.evaluation is None or self.evaluation.status is not EvaluationStatus.validated
        ):
            blockers.append(
                f"trust={self.governance.trust.value} requires evaluation.status == validated "
                "(run `n4a-repository evaluate`)"
            )
        return blockers


def utc_date() -> str:
    """Return today's date as an ISO ``YYYY-MM-DD`` string (UTC)."""
    return _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%d")


def descriptor_from_dict(data: dict[str, Any]) -> PipelineDescriptor:
    """Validate a raw mapping into a :class:`PipelineDescriptor`."""
    return PipelineDescriptor.model_validate(data)
