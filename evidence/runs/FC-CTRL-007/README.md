# FC-CTRL-007 evidence

Coordination evidence for the transition from the integrated settlement
runtime to the authorized close, expiry, epoch, and refund work item.

## Immutable references

- baseline: `74359f6ac81e75d595f934ed3e03428a45a2dafa`
- FC-PROTO-004 reviewed head: `47a5c9f9160e5f0562058fd3e18936f24c222ab3`
- FC-PROTO-004 merge commit: `74359f6ac81e75d595f934ed3e03428a45a2dafa`
- coordination implementation: `54157e0934fe2ea37cb24feba3ebaa4d242e324a`

## Result

- `FC-PROTO-004` is `done`;
- `FC-PROTO-005` remains `ready`;
- the FC-PROTO-005 baseline must contain the settlement merge;
- the expiry-v1 ADR and provenance ledger are explicitly authorized paths;
- no on-chain or consumer gate was advanced.

## Reproduction

```text
python scripts/check_channel_foundation.py
python -m pytest tests/channels/test_foundation_contracts.py -q
git diff --check
```
