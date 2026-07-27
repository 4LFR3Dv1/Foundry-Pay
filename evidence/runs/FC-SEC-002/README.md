# FC-SEC-002 evidence

This pack records self-validation of signed-preimage domain separation,
semantic type separation, downgrade resistance, lifecycle policy, and
rejection effects.

The test model permits a bounded append-only rejection audit event. Rejected
inputs produce zero economic effect, zero authority advancement, and zero
channel lifecycle transition.

## Reproduce

```bash
python -m pytest tests/channels/security/replay
npm test --prefix packages/channel-protocol/typescript
python tests/channels/security/replay/run_cross_language.py \
  --output-root .fc-sec-002-local
```

The last command requires Python, Node.js, and Rust toolchains. CI uses the
pinned FC-PROTO-007 versions. The committed negative expectation vector is not
read by any runner; language-specific tests compare runner output only after
execution.

## Limits

- self-validated; no independent external security review was performed;
- offline signed-preimage and authority-effect model only;
- fixtures do not contain independently verifiable Ed25519 key material;
- no ChannelVault, RPC, wallet, devnet, mainnet, custody, or real-value claim;
- local-validator experimentation is allowed;
- devnet fixture, mainnet, and real value remain blocked.
