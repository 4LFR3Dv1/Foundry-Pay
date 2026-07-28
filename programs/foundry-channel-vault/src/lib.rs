//! Experimental, local-validator-only account representation for Foundry Channels.
//!
//! This crate intentionally contains no program entrypoint, instructions, CPI,
//! token transfers, or signature verification.

pub mod pda;
pub mod state;
pub mod vault;

pub use pda::{derive_channel_pda, verify_channel_pda, CHANNEL_SEED};
pub use state::{
    deserialize_program_account, ChannelState, ChannelStateError, EnvironmentCode, NetworkCode,
    StatusCode, CHANNEL_STATE_DISCRIMINATOR, CHANNEL_STATE_FIELDS, CHANNEL_STATE_RESERVED_BYTES,
    CHANNEL_STATE_SPACE, CHANNEL_STATE_VERSION_V1,
};
pub use vault::{
    associated_token_program_id, classic_token_program_id, derive_vault_address,
    token_2022_program_id, validate_vault_account, VaultAccountError, VaultAccountView,
};
