# FC-CTRL-028 evidence

The FC-SOL-003A artifact manifest contains both immutable evidence files and
source files analyzed at its functional commit. This coordination makes the
verification boundary explicit:

```text
evidence/runs/FC-SOL-003A/**
→ verify current immutable evidence bytes

all other artifact paths
→ verify bytes from FC-SOL-003A functional_head
```

In a shallow CI checkout, the verifier fetches only that exact commit before
reading its blobs.

No historical evidence file is regenerated.
