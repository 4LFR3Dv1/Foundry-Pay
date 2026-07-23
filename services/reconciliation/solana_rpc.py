"""Read-only Solana JSON-RPC snapshot reader for independent reconciliation."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from typing import Any

from .protocol import ReconciliationInvalid, raw_response_hash
from .sources import TransactionSnapshot

RpcTransport = Callable[[str, bytes], bytes]


def urllib_rpc_transport(endpoint: str, payload: bytes) -> bytes:
    """POST JSON-RPC without logging or persisting the credential-bearing URL."""

    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "accept": "application/json",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        return response.read()


class SolanaRpcSnapshotReader:
    """Provider-local parser used behind the source adapter boundary."""

    def __init__(
        self,
        endpoint: str,
        *,
        network: str = "solana:devnet",
        commitment: str = "confirmed",
        transport: RpcTransport = urllib_rpc_transport,
    ):
        if not endpoint:
            raise ReconciliationInvalid("RPC endpoint is required")
        if network != "solana:devnet":
            raise ReconciliationInvalid("RPC reader supports solana:devnet only")
        if commitment not in {"confirmed", "finalized"}:
            raise ReconciliationInvalid("unsupported RPC commitment")
        self._endpoint = endpoint
        self._network = network
        self._commitment = commitment
        self._transport = transport

    def read(
        self,
        *,
        signature: str,
        source_account: str,
        destination_account: str,
    ) -> TransactionSnapshot:
        transaction_payload = _request(
            1,
            "getTransaction",
            [
                signature,
                {
                    "encoding": "jsonParsed",
                    "commitment": self._commitment,
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        )
        status_payload = _request(
            2,
            "getSignatureStatuses",
            [[signature], {"searchTransactionHistory": True}],
        )
        transaction_raw = self._transport(self._endpoint, transaction_payload)
        status_raw = self._transport(self._endpoint, status_payload)
        transaction = _rpc_result(transaction_raw, "getTransaction")
        statuses = _rpc_result(status_raw, "getSignatureStatuses")
        if transaction is None:
            raise ReconciliationInvalid("getTransaction returned no transaction")
        if not isinstance(statuses, dict):
            raise ReconciliationInvalid("getSignatureStatuses returned invalid result")
        values = statuses.get("value")
        if not isinstance(values, list) or len(values) != 1 or values[0] is None:
            raise ReconciliationInvalid("signature status is unavailable")
        status = values[0]
        confirmation_status = status.get("confirmationStatus")
        if confirmation_status not in {"confirmed", "finalized"}:
            raise ReconciliationInvalid("signature is not confirmed")

        message = _object(_object(transaction, "transaction"), "message")
        account_keys = _account_keys(message.get("accountKeys"))
        metadata = _object(transaction, "meta")
        before = _token_amounts(metadata.get("preTokenBalances"), account_keys)
        after = _token_amounts(metadata.get("postTokenBalances"), account_keys)
        for account in (source_account, destination_account):
            if account not in before or account not in after:
                raise ReconciliationInvalid(
                    f"transaction token balance is unavailable for account {account}"
                )

        error = metadata.get("err")
        transaction_error = (
            "none"
            if error is None
            else raw_response_hash(
                json.dumps(
                    error,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            )
        )
        slot = transaction.get("slot")
        if not isinstance(slot, int) or isinstance(slot, bool):
            raise ReconciliationInvalid("transaction slot is invalid")
        raw_bundle = (
            b"getTransaction\x00" + transaction_raw + b"\x00getSignatureStatuses\x00" + status_raw
        )
        return TransactionSnapshot(
            signature=signature,
            network=self._network,
            slot=slot,
            confirmation_status=confirmation_status,
            transaction_error=transaction_error,
            source_account=source_account,
            destination_account=destination_account,
            source_account_before=before[source_account],
            source_account_after=after[source_account],
            destination_account_before=before[destination_account],
            destination_account_after=after[destination_account],
            raw_response=raw_bundle,
        )


def _request(request_id: int, method: str, params: list[Any]) -> bytes:
    return json.dumps(
        {
            "id": request_id,
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _rpc_result(payload: bytes, method: str) -> Any:
    try:
        response = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReconciliationInvalid(f"{method} returned invalid JSON") from error
    if not isinstance(response, dict) or response.get("jsonrpc") != "2.0":
        raise ReconciliationInvalid(f"{method} returned invalid JSON-RPC")
    if "error" in response:
        raise ReconciliationInvalid(f"{method} returned an RPC error")
    if "result" not in response:
        raise ReconciliationInvalid(f"{method} returned no result")
    return response["result"]


def _object(value: Any, field: str) -> dict[str, Any]:
    child = value.get(field) if isinstance(value, dict) else None
    if not isinstance(child, dict):
        raise ReconciliationInvalid(f"transaction {field} is invalid")
    return child


def _account_keys(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ReconciliationInvalid("transaction account keys are invalid")
    keys: list[str] = []
    for item in value:
        key = item.get("pubkey") if isinstance(item, dict) else item
        if not isinstance(key, str):
            raise ReconciliationInvalid("transaction account key is invalid")
        keys.append(key)
    return keys


def _token_amounts(value: Any, account_keys: list[str]) -> dict[str, str]:
    if not isinstance(value, list):
        raise ReconciliationInvalid("transaction token balances are invalid")
    balances: dict[str, str] = {}
    for item in value:
        if not isinstance(item, dict):
            raise ReconciliationInvalid("transaction token balance is invalid")
        index = item.get("accountIndex")
        token_amount = item.get("uiTokenAmount")
        amount = token_amount.get("amount") if isinstance(token_amount, dict) else None
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or not 0 <= index < len(account_keys)
            or not isinstance(amount, str)
        ):
            raise ReconciliationInvalid("transaction token balance is invalid")
        balances[account_keys[index]] = amount
    return balances
