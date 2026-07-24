# Third-party notices

Foundry Pay is distributed under Apache-2.0 for content over which the licensor
holds the necessary rights. Third-party dependencies and materials remain
subject to their own licenses.

## External integration

Solana-Agent is an independent Apache-2.0 project. Foundry Pay contains a
reconstructed public conformance vector derived from the immutable Solana-Agent
revision recorded in `REUSE_LEDGER.yaml`; it does not include the Solana-Agent
runtime.

## Package dependencies

Python and Node package dependencies are installed from their respective
package registries and are not relicensed by Foundry Pay. Their authoritative
versions are recorded in `pyproject.toml` and
`packages/external-execution-protocol/typescript/package-lock.json`.

## Reference-only sources

Sources marked `reference-only` in `REUSE_LEDGER.yaml` have not been copied into
this repository. They remain excluded until ownership and compatible licensing
are documented.
