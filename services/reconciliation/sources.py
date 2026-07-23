"""Adapters that turn independently obtained snapshots into observations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from .protocol import (
    PROFILE,
    PROTOCOL_VERSION,
    SourceDescriptor,
    normalize_observation,
    raw_response_hash,
)


@dataclass(frozen=True)
class TransactionSnapshot:
    signature: str
    network: str
    slot: int
    confirmation_status: str
    transaction_error: str
    source_account: str
    destination_account: str
    source_account_before: str
    source_account_after: str
    destination_account_before: str
    destination_account_after: str
    raw_response: bytes


class SnapshotReader(Protocol):
    """Provider-specific reader and parser, implemented outside consensus."""

    def read(
        self,
        *,
        signature: str,
        source_account: str,
        destination_account: str,
    ) -> TransactionSnapshot: ...


class ObservationSource:
    def __init__(
        self,
        descriptor: SourceDescriptor,
        reader: SnapshotReader,
        *,
        now: Callable[[], datetime] | None = None,
    ):
        self.descriptor = descriptor
        self.reader = reader
        self._now = now or (lambda: datetime.now(UTC))

    def observe(
        self,
        *,
        signature: str,
        source_account: str,
        destination_account: str,
    ) -> dict:
        snapshot = self.reader.read(
            signature=signature,
            source_account=source_account,
            destination_account=destination_account,
        )
        observed_amount = int(snapshot.destination_account_after) - int(
            snapshot.destination_account_before
        )
        observation = {
            "type": "source_observation",
            "protocol_version": PROTOCOL_VERSION,
            "normalization_profile": PROFILE,
            **self.descriptor.__dict__,
            "queried_at": self._now()
            .astimezone(UTC)
            .replace(microsecond=0)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "signature": snapshot.signature,
            "network": snapshot.network,
            "slot": snapshot.slot,
            "confirmation_status": snapshot.confirmation_status,
            "transaction_error": snapshot.transaction_error,
            "source_account": snapshot.source_account,
            "destination_account": snapshot.destination_account,
            "source_account_before": snapshot.source_account_before,
            "source_account_after": snapshot.source_account_after,
            "destination_account_before": snapshot.destination_account_before,
            "destination_account_after": snapshot.destination_account_after,
            "observed_amount_base_units": str(observed_amount),
            "raw_response_hash": raw_response_hash(snapshot.raw_response),
        }
        return normalize_observation(observation)
