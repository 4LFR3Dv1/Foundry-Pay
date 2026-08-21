# FC-SOL-003B evidence

This evidence set records the runtime signed-preimage operability correction.
It does not record a Solana deployment or economic execution.

## Functional implementation

- work item: `FC-SOL-003B`
- pull request: `#76`
- functional head: `3876f26f155bfeecf322390c31543104aecc1ebe`
- validation CI run: `32494273091`
- CI merge ref tested: `1dec5d62d0fc008d6b575657f6cdc54db1f09d2d`

## What was demonstrated

1. A separate instruction contract version `2` exists while historical v1 remains intact.
2. The eight operation names/discriminators remain the same.
3. Initialization v2 carries the immutable state identity needed for later signed-object validation.
4. Voucher activation authority is derived from the exact FC-PROTO-006 sender-signed bytes, not duplicated economic args.
5. Initial recipient-binding authority is derived from the exact doubly-signed FC-PROTO-006 bytes, including destination and binding nonce.
6. The frozen Ed25519 layouts can yield the exact signed message without changing their offsets or instruction-position rule.
7. Hash, context, destination, mint, and binding-nonce substitutions fail closed in the Rust tests.
8. Existing Python/TypeScript/Rust protocol conformance remains green.

## CI observations

The GitHub Actions run completed successfully across every job.

The `protocol` job reported:

```text
Static checks                       passed
Secret guard                        passed (645 files scanned)
Python full protocol suite          576 passed
External Execution Protocol TS      8 passed
Channel Protocol TS                 20 passed
```

The separate conformance lanes also passed:

```text
conformance-python       passed
conformance-typescript   passed
conformance-rust         passed
conformance-compare      passed
conformance-poisoning    passed
```

The 576-test Python suite contains `test_foundation_contracts_and_gates_pass`,
which calls `scripts/check_channel_foundation.py::validate`, and the existing
Solana instruction-contract test, which executes:

```text
cargo test --locked --manifest-path programs/foundry-channel-vault/instruction-contract/Cargo.toml --lib
```

## Frozen-byte/source compatibility

Direct GitHub blob identity was checked between `main` and the functional
branch:

```text
v1 instruction source
programs/foundry-channel-vault/instruction-contract/src/instruction.rs
a2f71cf5cd5923260a34fc8f797688aa4bf658df

ChannelState source
programs/foundry-channel-vault/src/state.rs
d6e2f07e607051db4855a99b27adc2e4fda1c7d2
```

Both blob IDs are identical on `main` and `agent/solana/FC-SOL-003B`.
`CHANNEL_STATE_SPACE` remains `490`.

The functional tests consume the pre-existing FC-PROTO-006 positive canonical
vectors directly rather than creating replacement signer fixtures.

## Canonicality boundary

The new Rust validator is intentionally profile-specific. It validates exact
bytes for the frozen `ChannelVoucher` and initial `RecipientBinding` profiles.
It is not claimed as a general RFC 8785 implementation for arbitrary JSON.

## Maturity

```text
implementation     complete for FC-SOL-003B scope
self-validation    passed
external review    not performed
entrypoint         not implemented
CPI/transfers      not implemented
local execution    not claimed
devnet deployment  not authorized
mainnet            blocked
real value         blocked
```

`FC-SOL-006` remains blocked until this evidence and implementation are
integrated through review.
