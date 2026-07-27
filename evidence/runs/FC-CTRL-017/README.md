# FC-CTRL-017 evidence

This run records the distinction between forbidden economic or authority
effects and permitted rejection audit effects.

The existing voucher journal may durably record an invalid submission as
`rejected`. That observability is not verification, activation, authorization,
completion, or economic effect. Recipient binding continues to verify before
insertion.

External review was not performed. Devnet, mainnet, and real-value use remain
blocked.

## Reproduce

```text
python -m pytest --junitxml .fcctrl017-pytest-full.xml -p no:cacheprovider
python -m ruff check .
python -m ruff format --check .
python scripts/check_secrets.py
python evidence/runs/FC-CTRL-017/generate_evidence.py \
  --junit-source .fcctrl017-pytest-full.xml
```
