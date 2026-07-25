# FC-CTRL-006 evidence

This run reconciles the Foundry Channels work graph with the independently
reviewed offline gates integrated through `FC-SEC-003`.

## Immutable references

- baseline main: `ec8db6ba213d40718b3d9e5593826021d36e0e77`
- implementation commit: `20f9895a160a2482f4d55775e607684e0e710441`
- reviewed head: recorded by the pull request review after this evidence commit

Integrated gates recorded by the graph:

- `FC-PROTO-001`: `0911bb9d5128c4dc9dccf82437a0dce0c0b53896`
- `FC-PROTO-002`: `a27a0e3daf0ecf2d0f11471d3055283cf6859db7`
- `FC-PROTO-003`: `2a5a7f8392c5af96e59d19585a83578761c2606b`
- `FC-SEC-003`: `ec8db6ba213d40718b3d9e5593826021d36e0e77`

## Reproduction

```text
python scripts/check_channel_foundation.py
python -m pytest -q --junitxml evidence/runs/FC-CTRL-006/pytest-full.xml
python -m ruff check .
python -m ruff format --check .
python scripts/check_secrets.py
git diff --check
```

Observed:

- foundation/work-graph validation: passed;
- ready items: `FC-PROTO-004`, `FC-PROTO-005`, `FC-PROTO-006`,
  `FC-VAL-003`;
- ready items with incomplete dependencies: none;
- pytest: 294 collected, 283 passed, 11 expected skips, 0 failures;
- Ruff check and format: passed;
- secret guard: 248 files scanned, passed;
- diff check: passed.

The eleven skips require the optional pinned `SA-CHAOS-001` checkout and are
pre-existing. This coordination work does not claim those scenarios as newly
executed evidence.

## Boundary

This run unlocks offline protocol work only. `SA-CHAN-000` and `FC-FAIL-003`
remain blocked. It does not authorize or prove ChannelVault, Solana execution,
`SA-CHAN-001`, `FC-SEC-004`, `FC-SEC-005`, a deployed consumer frontend, human
validation, or exactly-once blockchain execution.
