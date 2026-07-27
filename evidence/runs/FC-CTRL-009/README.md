# FC-CTRL-009 evidence

The foundation close-race checker reads the legacy single-snapshot fields
directly. FC-PROTO-005 cannot introduce distinct request/freeze snapshots and
an exclusive activation deadline while leaving that checker unchanged.

This coordination item authorizes only:

```text
scripts/check_channel_foundation.py
tests/channels/test_foundation_contracts.py
```

for the FC-PROTO-005 migration. No checker or runtime behavior changes here.
