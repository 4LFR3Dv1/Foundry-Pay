# FC-CTRL-008 evidence

FC-PROTO-005 replaces the ambiguous legacy closure object with distinct request
and freeze snapshots. The foundation validator proved that the existing public
`close-race-v1.json` fixture must migrate with the schema. This coordination
item authorizes exactly that vector path before implementation.

Validation:

```text
python scripts/check_channel_foundation.py
git diff --check
```

Both checks passed before the contract migration. No runtime, schema, or vector
content is changed by this coordination item.
