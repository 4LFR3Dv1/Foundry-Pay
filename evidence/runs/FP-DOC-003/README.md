# FP-DOC-003 verification

## Outcome

Foundry Pay now has an explicit Apache-2.0 license, copyright attribution,
public/commercial boundary, external README, deterministic wallet-free
quickstart, and community contribution surfaces.

The rights holder confirmed:

- license: Apache License, Version 2.0;
- scope: all public repository content over which the rights holder has the
  necessary rights, subject to third-party licenses and attribution;
- copyright holder in `NOTICE`: Renan Melo.

## Verified source

- implementation commit:
  `62915636b9ffed9b77811afa417f1ae81b1c9004`
- branch: `agent/docs/FP-DOC-003`
- verification date: `2026-07-24`

## License verification

The root `LICENSE` was compared with the canonical `apache-2.0` body returned by
the GitHub Licenses API:

```text
ExactTextMatch : True
LocalChars     : 11356
CanonicalChars : 11356
```

A wheel built from the implementation commit contains:

```text
foundry_external_execution_protocol-0.1.0.dist-info/licenses/LICENSE
foundry_external_execution_protocol-0.1.0.dist-info/licenses/NOTICE
License-Expression: Apache-2.0
License-File: LICENSE
License-File: NOTICE
```

The TypeScript package and lockfile also declare `Apache-2.0`.

## Clean onboarding verification

The documented flow was executed in a newly created Python 3.14.5 virtual
environment using only:

```text
python -m pip install -e .
python examples/local_proof.py
```

Elapsed time, including environment creation and package installation:

```text
CLEAN_QUICKSTART_SECONDS=12.31
```

Observed proof:

```json
{
  "economic_effect_count": 1,
  "execution_commitment_hash": "sha256:3ea9fcafc9832aa91fd3521f8c1295c39639498400bbfbb5ef2cdd42f16d06d3",
  "execution_request_id": "exec_quickstart_001",
  "may_rematerialize": false,
  "prepared_message_hash": "sha256:9c64ed7b5f49bf29220cd037b429278ee0b8486f6d2e4965b15ca8d3e7db9286",
  "receipt_hash": "sha256:30921a02c0f7a1d8a2a6e5055d588df6c4d31726f2c00e5c443be1dd6c797b45",
  "recovery_outcome": "confirmed",
  "replay_blocked": true,
  "response_lost_after_commit": true
}
```

No wallet, Solana CLI, RPC endpoint, token, or funds were used.

## Quality gates

```text
LOCAL_MARKDOWN_LINKS=OK
git diff --check: passed
python -m ruff check .: passed
python -m ruff format --check .: 37 files already formatted
python -m pytest: 105 passed, 11 skipped
python scripts/check_secrets.py: 151 files scanned, passed
npm test --prefix packages/external-execution-protocol/typescript: 8 passed
```

The 11 locally skipped tests require the pinned external Solana-Agent chaos
checkout. CI fetches that immutable checkout before running the complete
protocol gate.

## Residual gates

- GitHub must detect the new root license after the branch is merged.
- CI must validate the pinned Python 3.11 and external chaos path.
- Independent security review and production readiness remain explicitly open.
- Private vulnerability reporting should be enabled in repository settings
  before broad external adoption; `SECURITY.md` provides a fallback contact
  procedure.
