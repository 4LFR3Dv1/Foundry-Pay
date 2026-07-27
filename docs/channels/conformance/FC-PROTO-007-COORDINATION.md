# FC-PROTO-007 coordination contract

## Fixed baseline

```text
repository: 4LFR3Dv1/Foundry-Pay
baseline: 17b656cbdd6ae53cece9cebb9123058c03e67b82
contains:
  FC-PROTO-006 merge 959cd8db597510a5fc58ee6acd421a1ae6bacb42
  FP-DOC-004 merge 17b656cbdd6ae53cece9cebb9123058c03e67b82
```

No functional work may start from an earlier baseline.

## Fixed toolchains

The machine-readable authority is
[`toolchains.v1.json`](../../../contracts/channel/conformance/toolchains.v1.json).

| Implementation | Runtime/compiler | RFC 8785 dependency |
| --- | --- | --- |
| Python | CPython 3.11.9 | `rfc8785==0.1.4` |
| TypeScript | Node.js 24.15.0, TypeScript 5.9.3 | `canonicalize==3.0.0` |
| Rust | rustc/cargo 1.85.1, edition 2024 | `serde_json_canonicalizer==0.3.2` |

Package managers must install from committed lockfiles. The functional PR must
record exact resolved transitive dependencies and registry integrity metadata.

## Normative inputs

All runners receive:

```text
--registry-root contracts/channel/canonicalization
```

They must load `manifest.v1.json`, then process every listed positive and
negative vector exactly once in lexicographic `vector_id` order.

Positive JSON profiles compute from `source_json`. Raw-byte and evidence
profiles compute from `source_bytes_hex`. Expected bytes, Base64, length, and
SHA-256 are comparator expectations only.

## Runner interface

Each runner exposes:

```text
<runner> --registry-root <path>
```

Standard output contains only UTF-8 JSON Lines conforming to
[`runner-result.v1.schema.json`](../../../contracts/channel/conformance/runner-result.v1.schema.json).
Diagnostics go to standard error.

Expected vector rejection is a successful runner observation and does not make
the runner exit nonzero. Internal errors, missing vectors, duplicate results,
malformed contracts, and incomplete processing must exit nonzero.

Results are ordered by `vector_id`. Exactly 28 results are required for the
current registry:

```text
8 positive
20 negative
```

## Comparator

The comparator receives three completed streams and:

1. validates every line against the closed result schema;
2. requires implementations `python`, `typescript`, and `rust` exactly once;
3. requires the same complete vector set and order;
4. compares positive decision, bytes, Base64, length, and SHA-256;
5. compares negative decision, rejection stage, and rejection code;
6. compares all results with the frozen vector expectations;
7. fails on missing, duplicate, extra, malformed, or out-of-order results.

It performs no protocol computation.

## CI shape

```text
python-conformance
typescript-conformance
rust-conformance
        |
        v
download three immutable result artifacts
        |
        v
cross-language comparator
        |
        v
poisoning proof + artifact manifest
```

The functional PR may initially keep these steps in one job if each runner is
still executed as an isolated process and all three output files exist before
the comparator starts. Separate CI jobs are preferred for stronger operational
independence.

## Rejection matrix

The machine-readable authority is
[`rejection-codes.v1.json`](../../../contracts/channel/conformance/rejection-codes.v1.json).
Agreement on only `accept` or `reject` is insufficient.

## Reserved functional paths

FC-PROTO-007 may change only:

```text
.github/workflows/ci.yml
.agents/tasks/FC-PROTO-007.yaml
docs/channels/WORK_GRAPH.md
docs/channels/work-items.yaml
packages/channel-protocol/python/**
packages/channel-protocol/typescript/**
packages/channel-protocol/rust/**
contracts/channel/conformance/**
tests/channels/conformance/**
evidence/runs/FC-PROTO-007/**
provenance/REUSE_LEDGER.yaml
provenance/THIRD_PARTY_NOTICES.md
```

The frozen artifacts under `contracts/channel/canonicalization/**` are
read-only inputs. Any required mutation is a stop condition and requires a
separate versioning decision.
