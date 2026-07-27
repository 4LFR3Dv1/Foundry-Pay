# FC-CTRL-016 evidence

This run proves that the FC-SEC-002 adversarial and lifecycle contract was
frozen against the governed `main` baseline without changing protocol runtime,
canonicalization registries, conformance vectors, or deployment authorization.

The resulting contract permits self-validated offline and local-validator
experimentation. External review was not performed. Devnet, mainnet, and
real-value use remain blocked.

## Reproduce

```text
python -m pytest --junitxml .fcctrl016-pytest-full.xml -p no:cacheprovider
python -m ruff check .
python -m ruff format --check .
python scripts/check_secrets.py
python evidence/runs/FC-CTRL-016/generate_evidence.py \
  --junit-source .fcctrl016-pytest-full.xml
```

The generator validates the work-item projection, asserts forbidden
implementation paths were untouched, copies the executed JUnit report, and
hashes the published artifacts.
