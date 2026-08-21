//! Deterministic Foundry Channels instruction contracts and fixtures.
//!
//! This crate has no program entrypoint, economic handler, CPI, token transfer,
//! deployment support, or production signature verifier.

pub mod contract;
pub mod ed25519;
pub mod instruction;
pub mod lifecycle;
mod runtime_v2;
mod runtime_v2_authority;

pub use contract::{
    account_contract, event_contract, AccountContract, AccountRequirement, AuthorityKind,
    ChannelEventCode, ContractErrorCode, InstructionContract, ACCOUNT_CONTRACTS, ERROR_REGISTRY,
    EVENT_CONTRACTS,
};
pub use ed25519::{
    build_binding_ed25519_data, build_voucher_ed25519_data, extract_binding_ed25519_message,
    extract_voucher_ed25519_message, verify_binding_ed25519_data, verify_voucher_ed25519_data,
    Ed25519ContractError, ExtractedBindingMessage, ED25519_PROGRAM_ID_BYTES,
};
pub use instruction::{
    instruction_discriminator, ChannelInstruction, InstructionDecodeError, InstructionKind,
    INSTRUCTION_CONTRACT_VERSION_V1,
};
pub use lifecycle::{
    derive_lifecycle_phase, validate_claim_deadline, LifecycleContractError, LifecyclePhase,
    MAX_CLAIM_WINDOW_SECONDS, MIN_CLAIM_WINDOW_SECONDS,
};
pub use runtime_v2::{
    channel_id_hash, decode_binding_nonce_u64, encode_binding_nonce_u64, RuntimeAuthorityError,
    RuntimeInstructionV2, RuntimeInstructionV2DecodeError, VerifiedRecipientBindingAuthority,
    VerifiedVoucherAuthority, INITIAL_BINDING_NONCE, INITIAL_LATEST_VOUCHER_HASH,
    INSTRUCTION_CONTRACT_VERSION_V2, JSON_SAFE_UNSIGNED_MAX,
};
pub use runtime_v2_authority::{
    verify_initialize_v2, verify_recipient_binding_signed_message, verify_voucher_signed_message,
    VerifiedInitializationV2,
};

// The maintainer's Windows application-control policy permits crate test
// binaries but can block newly built example executables. Including the same
// Rust generator in the test harness preserves one source of truth.
#[cfg(test)]
#[path = "../examples/generate_instruction_vectors.rs"]
mod generate_instruction_vectors;
