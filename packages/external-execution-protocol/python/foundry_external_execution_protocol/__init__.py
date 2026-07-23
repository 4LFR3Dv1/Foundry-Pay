"""Reference implementation of Foundry Pay protocol canonicalization."""

from .canonicalization import (
    DomainNormalizationError,
    canonicalize,
    economic_plan_hash,
    execution_commitment_hash,
    normalize_economic_plan,
    prepared_message_hash,
    sha256_digest,
    simulation_attestation_hash,
)
from .fake_executor import (
    AuthorizationInvalid,
    AuthorizationMismatch,
    AuthorizationReplay,
    FakeAuthorizationAuthority,
    FakeExternalExecutor,
    FakeExecutorError,
    IdempotencyConflict,
    ObligationAlreadyExecuted,
    ResponseLost,
)

__all__ = [
    "DomainNormalizationError",
    "AuthorizationInvalid",
    "AuthorizationMismatch",
    "AuthorizationReplay",
    "FakeAuthorizationAuthority",
    "FakeExternalExecutor",
    "FakeExecutorError",
    "IdempotencyConflict",
    "ObligationAlreadyExecuted",
    "ResponseLost",
    "canonicalize",
    "economic_plan_hash",
    "execution_commitment_hash",
    "normalize_economic_plan",
    "prepared_message_hash",
    "sha256_digest",
    "simulation_attestation_hash",
]
