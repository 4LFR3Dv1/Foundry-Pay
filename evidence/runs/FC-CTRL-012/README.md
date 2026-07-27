# FC-CTRL-012 evidence

The FC-PROTO-006 full regression exposed a pytest import-file mismatch because
both `tests/channels/test_canonicalization.py` and
`tests/protocol/test_canonicalization.py` otherwise import as the same top-level
module.

This coordination-only item authorizes an empty `tests/channels/__init__.py`
package marker. It changes no runtime behavior, test assertion, protocol gate,
or product gate.
