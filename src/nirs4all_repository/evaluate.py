# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Functional evaluation of a pipeline against its reference dataset.

This is the "tested pipelines" promise: re-run a recipe against a pinned reference
dataset (from ``nirs4all-datasets``) and compare the achieved metric to the descriptor's
``evaluation.expected`` within tolerance. It needs ``nirs4all`` (and the dataset), so it
is imported lazily and runs only as an opt-in job / locally — never in the hermetic CI
gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .bridge import Pipeline
from .schema import EvaluationStatus, Framework, ReferenceSource

#: Map a metric name to the matching ``RunResult`` accessor.
_METRIC_ACCESSORS = {
    "rmse": "best_rmse",
    "r2": "best_r2",
    "accuracy": "best_accuracy",
}


class EvaluationError(Exception):
    """Raised when a pipeline cannot be functionally evaluated."""


@dataclass
class EvaluationOutcome:
    """The result of a functional evaluation."""

    pipeline_id: str
    status: EvaluationStatus
    computed: dict[str, float] = field(default_factory=dict)
    comparisons: list[str] = field(default_factory=list)
    message: str = ""


def _load_reference_dataset(pipeline: Pipeline) -> Any:
    reference = pipeline.descriptor.reference
    if reference is None:
        raise EvaluationError(f"pipeline {pipeline.id!r} has no reference dataset to evaluate against")
    if reference.source is ReferenceSource.nirs4all_datasets:
        try:
            import nirs4all_datasets
        except Exception as exc:  # pragma: no cover - optional dep
            raise EvaluationError("nirs4all-datasets is required to resolve the reference dataset") from exc
        dataset = nirs4all_datasets.get(reference.name)
        bridge = getattr(dataset, "to_nirs4all", None)
        return bridge() if callable(bridge) else dataset
    raise EvaluationError(f"reference source {reference.source.value!r} is not supported for automatic evaluation yet")


def _metric_value(result: Any, metric: str) -> float:
    accessor = _METRIC_ACCESSORS.get(metric.lower())
    if accessor and hasattr(result, accessor):
        return float(getattr(result, accessor))
    best = getattr(result, "best", {}) or {}
    if metric in best and best[metric] is not None:
        return float(best[metric])
    return float(getattr(result, "best_score", float("nan")))


def evaluate_pipeline(pipeline: Pipeline) -> EvaluationOutcome:
    """Run *pipeline* against its reference dataset and compare to expected metrics."""
    descriptor = pipeline.descriptor
    if descriptor.framework is not Framework.nirs4all:
        raise EvaluationError("automatic evaluation currently supports nirs4all pipelines only")
    if descriptor.evaluation is None:
        raise EvaluationError(f"pipeline {pipeline.id!r} declares no expected metrics")

    try:
        import nirs4all
    except Exception as exc:  # pragma: no cover - optional dep
        raise EvaluationError("nirs4all is required for functional evaluation") from exc

    dataset = _load_reference_dataset(pipeline)
    result = nirs4all.run(pipeline.to_nirs4all(), dataset)

    metric = descriptor.evaluation.metric
    achieved = _metric_value(result, metric)
    outcome = EvaluationOutcome(pipeline_id=pipeline.id, status=EvaluationStatus.validated)
    outcome.computed[metric] = achieved

    passed = True
    for partition, expected in descriptor.evaluation.expected.items():
        within = abs(achieved - expected.value) <= expected.tol
        outcome.comparisons.append(
            f"{partition}: achieved {achieved:.4f} vs expected {expected.value:.4f} ±{expected.tol:.4f} "
            f"=> {'ok' if within else 'FAIL'}"
        )
        passed = passed and within

    outcome.status = EvaluationStatus.validated if passed else EvaluationStatus.failed
    outcome.message = "all metrics within tolerance" if passed else "one or more metrics out of tolerance"
    return outcome
