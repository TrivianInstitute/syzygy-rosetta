"""Execution-boundary primitives for Syzygy Rosetta 2.1.

A system can respect authority in principle while still making intervention
causally ineffective if correction arrives after the last alterable boundary.
This module makes that boundary explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Union


class ExecutionStage(IntEnum):
    PROPOSED = 0
    AUTHORIZED = 1
    QUEUED = 2
    DISPATCHED = 3
    COMMITTED = 4
    IRREVERSIBLE = 5


@dataclass(frozen=True)
class ExecutionBoundary:
    """Declares the last stage at which intervention can still alter outcome.

    The boundary is inclusive: if ``current_stage`` equals
    ``last_correctable_stage``, a legitimate correction is still considered
    causally effective.
    """

    action_id: str
    last_correctable_stage: ExecutionStage

    def __post_init__(self) -> None:
        if not self.action_id.strip():
            raise ValueError("action_id must be non-empty")


def _coerce_stage(stage: Union[ExecutionStage, str, int]) -> ExecutionStage:
    if isinstance(stage, ExecutionStage):
        return stage
    if isinstance(stage, str):
        try:
            return ExecutionStage[stage.strip().upper()]
        except KeyError as exc:
            raise ValueError(f"unknown execution stage: {stage}") from exc
    try:
        return ExecutionStage(stage)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"unknown execution stage: {stage}") from exc


def last_correctable_boundary(boundary: ExecutionBoundary) -> ExecutionStage:
    return boundary.last_correctable_stage


def can_correction_still_change_outcome(
    boundary: ExecutionBoundary,
    current_stage: Union[ExecutionStage, str, int],
) -> bool:
    """Return True only while correction is still inside the declared window."""

    stage = _coerce_stage(current_stage)
    return stage <= boundary.last_correctable_stage


def intervention_window_status(
    boundary: ExecutionBoundary,
    current_stage: Union[ExecutionStage, str, int],
) -> str:
    """Human-readable reference status for observability and audit logs."""

    stage = _coerce_stage(current_stage)
    if can_correction_still_change_outcome(boundary, stage):
        return "correctable"
    return "past_last_correctable_boundary"
