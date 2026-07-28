//! Deterministic FC-SOL-003 instruction contracts and fixtures.
//!
//! This crate has no program entrypoint, economic handler, CPI, token transfer,
//! deployment support, or production signature verifier.

pub mod contract;
pub mod ed25519;
pub mod instruction;
pub mod lifecycle;

pub use contract::{
    account_contract, event_contract, AccountContract, AccountRequirement, AuthorityKind,
    ChannelEventCode, ContractErrorCode, InstructionContract, ACCOUNT_CONTRACTS, ERROR_REGISTRY,
    EVENT_CONTRACTS,
};
pub use ed25519::{
    build_binding_ed25519_data, build_voucher_ed25519_data, verify_binding_ed25519_data,
    verify_voucher_ed25519_data, Ed25519ContractError, ED25519_PROGRAM_ID_BYTES,
};
pub use instruction::{
    instruction_discriminator, ChannelInstruction, InstructionDecodeError, InstructionKind,
    INSTRUCTION_CONTRACT_VERSION_V1,
};
pub use lifecycle::{derive_lifecycle_phase, LifecycleContractError, LifecyclePhase};

// The maintainer's Windows application-control policy permits crate test
// binaries but can block newly built example executables. Including the same
// Rust generator in the test harness preserves one source of truth.
#[cfg(test)]
#[path = "../examples/generate_instruction_vectors.rs"]
mod generate_instruction_vectors;
