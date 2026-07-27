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

Python, Node, and Rust package dependencies are installed from their respective
package registries and are not relicensed by Foundry Pay. Their authoritative
versions are recorded in `pyproject.toml`, package lockfiles, and Cargo
lockfiles.

FC-PROTO-007 uses the following independently implemented canonicalization
libraries against the same frozen Foundry Channels vectors:

- `rfc8785` 0.1.4 (Apache-2.0) for Python;
- `canonicalize` 3.0.0 (Apache-2.0) for TypeScript;
- `serde_json_canonicalizer` 0.3.2 (MIT) for Rust.

Their inclusion demonstrates cross-language conformance; no library is treated
as the authority for another implementation.

## Reference-only sources

Sources marked `reference-only` in `REUSE_LEDGER.yaml` have not been copied into
this repository. They remain excluded until ownership and compatible licensing
are documented.
