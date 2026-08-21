# FC-SOL-006 evidence

Status: **partial implementation evidence — work item remains active**

This directory begins the evidence lineage for the operational ChannelVault
work item. It does not certify local-validator or devnet execution.

## First executable slice

Functional head:

`c76f0264ddfaed3c9caeee7876092d4aa9bd2ae2`

Pull request: `#78`

PR CI run: `32497047070`

Observed on GitHub Actions:

- repository pytest: `578 passed`;
- executable `foundry-channel-vault-program` host suite invoked through pytest
  and returned success;
- TypeScript External Execution Protocol: `8 passed`;
- TypeScript Channel Protocol: `20 passed`;
- Python/TypeScript/Rust conformance lanes: passed;
- poisoning-independence lane: passed;
- cross-language comparison lane: passed;
- secret guard: `650 files scanned`, passed.

The executable program slice currently contains real handlers for:

1. `activate_voucher`;
2. `bind_recipient`;
3. `request_close`.

The remaining operations intentionally fail closed until System/SPL CPI and
closure semantics are implemented and exercised.

## Preserved frozen material

This slice does not modify:

- `CHANNEL_STATE_SPACE = 490`;
- ChannelState discriminator/offsets;
- channel PDA seeds;
- FC-PROTO-006 canonical signed payloads;
- v1 instruction serialization;
- the eight operation names/discriminators.

## Evidence classification

```text
host compile/test                 observed
program entrypoint                implemented
real AccountInfo handlers         implemented for 3/8 operations
instructions-sysvar integration   implemented, host compiled
Clock integration                 implemented, host compiled
System Program CPI                not implemented
classic SPL Token CPI             not implemented
local-validator execution         not yet observed
SBF artifact                      not yet certified
Program ID                        not assigned/authorized
devnet deployment                 not performed
```

No item below `host compile/test` is to be promoted to deployment evidence
without a separate observed run.
