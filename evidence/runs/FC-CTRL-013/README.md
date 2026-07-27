# FC-CTRL-013 evidence

This coordination item records the completed FC-PROTO-006 integration without
changing canonical bytes, protocol runtime, or any on-chain or product gate.

```text
PR: 30
approved functional head: 835de5c9f2ed6c5ee0c6a2001ec63193e57eab7c
final evidence head: a396719a04ac6520a129850e5c402301fa2c3d68
merge commit: 959cd8db597510a5fc58ee6acd421a1ae6bacb42
main CI run: 30237524518
main CI result: passed
```

The public review history preserves two `REQUEST_CHANGES` decisions and the
final independent `APPROVE`. The final review reproduced 54/54 artifact hashes
and byte lengths, 23/23 registered schemas, all eight positive vectors, and the
full 461-pass regression.

FC-PROTO-007 and FC-SEC-002 become ready because their declared dependencies
are complete. FC-VAL-003 remains ready but unexecuted. ChannelVault, on-chain
execution, consumer product, and production gates remain blocked.
