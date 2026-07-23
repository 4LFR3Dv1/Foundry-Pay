"""Deterministic distributed-failure laboratory."""

from .lab import (
    BroadcastOutcomeUnknown,
    BroadcastUnavailable,
    DurableExecutionLab,
    FailureLabInvalid,
    InjectedCrash,
    SimulatedChain,
)
from .matrix import run_failure_matrix, write_failure_evidence

__all__ = [
    "BroadcastOutcomeUnknown",
    "BroadcastUnavailable",
    "DurableExecutionLab",
    "FailureLabInvalid",
    "InjectedCrash",
    "SimulatedChain",
    "run_failure_matrix",
    "write_failure_evidence",
]
