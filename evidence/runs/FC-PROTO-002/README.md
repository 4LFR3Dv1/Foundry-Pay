# FC-PROTO-002 evidence

Baseline:
`c9f66437c055143cf48e7de0f06443377737b024`

Implementation commit:
`dbf044a12f18741cdcdfbedd958ff03a405d6d8a`

Independent-review remediation commit:
`d3f30f433838067549f6a9892a15bb8630351270`

Second review remediation commit:
`7405a6ddff135c36d6341daf8c275fc62eef778d`

Scope:

- closed `ChannelVoucher` v1 validation;
- RFC 8785 canonical payload bytes;
- SHA-256 over the closed payload, whose required
  `foundry.channels.voucher` member provides signed-object domain separation;
- injected sender-signature verification over the exact canonical bytes;
- full replay binding across environment, network, genesis, program, channel,
  account, epoch, sender, recipient claim key, and mint;
- monotonic sequence and cumulative-total verification;
- funding, refund, policy, issuance-time, voucher-expiry, and channel-expiry
  bounds;
- coherent zero/non-zero activated snapshot and voucher-value guards;
- activation-request revalidation against current context and expiry;
- positive-u64 schema/runtime agreement for cumulative authorization;
- sender-signature reverification before `activation_requested`;
- retryable operational signature-verifier failures;
- monotonic journal timestamps and deterministically closed SQLite connections;
- SQLite journal with transactional restart and concurrency behavior.

Ledger states are intentionally limited to:

```text
issued
verified
activation_requested
rejected
```

`issued` records the sender-claimed signed object before local verification. It
is not an economic right. `verified` means the offline checks passed.
`activation_requested` remains a request. The ledger contains no `activated`
state or activation method; only the future ChannelVault may establish that
authoritative state.

Verification:

| Command | Result |
|---|---|
| `python -m pytest tests/channels/test_voucher.py tests/channels/test_channel.py tests/channels/test_foundation_contracts.py` | 130 passed |
| `python -m pytest` | 235 passed, 11 skipped |
| `python -m ruff format --check .` | passed |
| `python -m ruff check .` | passed |
| `python scripts/check_secrets.py` | 223 files passed |
| `npm ci && npm test` in external protocol TypeScript package | 8 passed; 0 vulnerabilities |

Eight shared negative voucher vectors are loaded by the Python suite and
must produce their declared stable error codes. Generated JUnit evidence is in
`pytest-full.xml`.

Security limitations:

- signature verification is injected; this PR does not choose production key
  custody or a cryptographic provider;
- caller-supplied `VoucherContext` must originate from an authoritative source;
- the ledger is a deterministic reference implementation, not ChannelVault;
- it does not prove that an issued voucher is globally latest;
- no Solana RPC, wallet, signer, Cloud, or on-chain operation occurs.

Independent reviews requested changes. They are implemented in `d3f30f4...`
and `7405a6d...`. Final independent approval is still required before merge
and before FC-PROTO-004, FC-PROTO-005, FC-PROTO-006, or money-moving work.
