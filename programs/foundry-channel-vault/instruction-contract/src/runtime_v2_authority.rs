//! Strict public FC-SOL-003B authority boundary.
//!
//! `runtime_v2` contains the deterministic codec and profile-local parsing
//! machinery. This module is the public surface intended for FC-SOL-006: it
//! closes initialization invariants and schema constraints before any future
//! runtime is allowed to consume returned authority.

use foundry_channel_vault_account_model::{ChannelState, EnvironmentCode};
use foundry_channel_vault_account_model::state::KNOWN_POLICY_FLAGS;
use solana_pubkey::Pubkey;

use crate::runtime_v2::{
    self, encode_binding_nonce_u64, RuntimeAuthorityError, RuntimeInstructionV2,
    VerifiedRecipientBindingAuthority, VerifiedVoucherAuthority, INITIAL_BINDING_NONCE,
    INITIAL_LATEST_VOUCHER_HASH,
};

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct VerifiedInitializationV2 {
    pub genesis_hash: [u8; 32],
    pub channel_id_hash: [u8; 32],
    pub environment: u8,
    pub policy_flags: u32,
    pub binding_nonce_slot: [u8; 32],
    pub latest_activated_voucher_hash: [u8; 32],
}

pub fn verify_initialize_v2(
    instruction: &RuntimeInstructionV2,
) -> Result<VerifiedInitializationV2, RuntimeAuthorityError> {
    let RuntimeInstructionV2::InitializeChannel {
        genesis_hash,
        channel_id_hash,
        environment,
        policy_flags,
        binding_nonce,
        ..
    } = instruction
    else {
        return Err(RuntimeAuthorityError::InvalidField("instruction_kind"));
    };

    if *environment != EnvironmentCode::DevnetFixture as u8 {
        return Err(RuntimeAuthorityError::UnsupportedEnvironment);
    }
    if *policy_flags & !KNOWN_POLICY_FLAGS != 0 {
        return Err(RuntimeAuthorityError::InvalidField("policy_flags"));
    }
    if *binding_nonce != INITIAL_BINDING_NONCE {
        return Err(RuntimeAuthorityError::InvalidField("binding_nonce"));
    }
    if *genesis_hash == [0; 32] {
        return Err(RuntimeAuthorityError::InvalidField("genesis_hash"));
    }
    if *channel_id_hash == [0; 32] {
        return Err(RuntimeAuthorityError::InvalidField("channel_id_hash"));
    }

    Ok(VerifiedInitializationV2 {
        genesis_hash: *genesis_hash,
        channel_id_hash: *channel_id_hash,
        environment: *environment,
        policy_flags: *policy_flags,
        binding_nonce_slot: encode_binding_nonce_u64(*binding_nonce),
        latest_activated_voucher_hash: INITIAL_LATEST_VOUCHER_HASH,
    })
}

pub fn verify_voucher_signed_message(
    message: &[u8],
    expected_voucher_hash: [u8; 32],
    state: &ChannelState,
    program_id: &Pubkey,
    channel_account: &Pubkey,
) -> Result<VerifiedVoucherAuthority, RuntimeAuthorityError> {
    let verified = runtime_v2::verify_voucher_signed_message(
        message,
        expected_voucher_hash,
        state,
        program_id,
        channel_account,
    )?;
    if verified.cumulative_authorized == 0 {
        return Err(RuntimeAuthorityError::InvalidField(
            "cumulative_authorized_base_units",
        ));
    }
    Ok(verified)
}

pub fn verify_recipient_binding_signed_message(
    message: &[u8],
    expected_binding_hash: [u8; 32],
    expected_ed25519_destination: &Pubkey,
    state: &ChannelState,
    program_id: &Pubkey,
    channel_account: &Pubkey,
) -> Result<VerifiedRecipientBindingAuthority, RuntimeAuthorityError> {
    runtime_v2::verify_recipient_binding_signed_message(
        message,
        expected_binding_hash,
        expected_ed25519_destination,
        state,
        program_id,
        channel_account,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{channel_id_hash, RuntimeInstructionV2};
    use foundry_channel_vault_account_model::{
        NetworkCode, StatusCode, CHANNEL_STATE_RESERVED_BYTES, CHANNEL_STATE_VERSION_V1,
    };
    use serde_json::Value;
    use sha2::{Digest, Sha256};
    use std::str::FromStr;

    const VOUCHER_VECTOR: &str = include_str!(
        "../../../../contracts/channel/canonicalization/positive/voucher-payload-v1.json"
    );

    #[test]
    fn initialize_v2_closes_beta_environment_policy_and_genesis_values() {
        let valid = RuntimeInstructionV2::InitializeChannel {
            channel_nonce: [1; 32],
            recipient_claim_pubkey: Pubkey::new_from_array([2; 32]),
            decimals: 6,
            channel_expiry: 1_800_000_000,
            genesis_hash: [3; 32],
            channel_id_hash: [4; 32],
            environment: EnvironmentCode::DevnetFixture as u8,
            policy_flags: KNOWN_POLICY_FLAGS,
            binding_nonce: INITIAL_BINDING_NONCE,
        };
        let verified = verify_initialize_v2(&valid).unwrap();
        assert_eq!(verified.genesis_hash, [3; 32]);
        assert_eq!(verified.channel_id_hash, [4; 32]);
        assert_eq!(verified.environment, EnvironmentCode::DevnetFixture as u8);
        assert_eq!(verified.policy_flags, KNOWN_POLICY_FLAGS);
        assert_eq!(
            verified.binding_nonce_slot,
            encode_binding_nonce_u64(INITIAL_BINDING_NONCE)
        );
        assert_eq!(verified.latest_activated_voucher_hash, [0; 32]);

        let local = RuntimeInstructionV2::InitializeChannel {
            environment: EnvironmentCode::LocalValidator as u8,
            ..valid.clone()
        };
        assert_eq!(
            verify_initialize_v2(&local),
            Err(RuntimeAuthorityError::UnsupportedEnvironment)
        );

        let unknown_flags = RuntimeInstructionV2::InitializeChannel {
            policy_flags: KNOWN_POLICY_FLAGS | (1 << 31),
            ..valid.clone()
        };
        assert_eq!(
            verify_initialize_v2(&unknown_flags),
            Err(RuntimeAuthorityError::InvalidField("policy_flags"))
        );

        let wrong_nonce = RuntimeInstructionV2::InitializeChannel {
            binding_nonce: 2,
            ..valid.clone()
        };
        assert_eq!(
            verify_initialize_v2(&wrong_nonce),
            Err(RuntimeAuthorityError::InvalidField("binding_nonce"))
        );

        let zero_genesis = RuntimeInstructionV2::InitializeChannel {
            genesis_hash: [0; 32],
            ..valid.clone()
        };
        assert_eq!(
            verify_initialize_v2(&zero_genesis),
            Err(RuntimeAuthorityError::InvalidField("genesis_hash"))
        );

        let zero_channel_id = RuntimeInstructionV2::InitializeChannel {
            channel_id_hash: [0; 32],
            ..valid
        };
        assert_eq!(
            verify_initialize_v2(&zero_channel_id),
            Err(RuntimeAuthorityError::InvalidField("channel_id_hash"))
        );
    }

    #[test]
    fn public_voucher_authority_rejects_zero_cumulative_total() {
        let vector: Value = serde_json::from_str(VOUCHER_VECTOR).unwrap();
        let projection = &vector["parsed_projection"];
        let program_id = Pubkey::from_str(projection["program_id"].as_str().unwrap()).unwrap();
        let channel_account =
            Pubkey::from_str(projection["channel_account"].as_str().unwrap()).unwrap();
        let state = voucher_state(projection);

        let mut payload = projection.clone();
        payload["cumulative_authorized_base_units"] = Value::String("0".into());
        let bytes = serde_json::to_vec(&payload).unwrap();
        let hash = sha256(&bytes);
        assert_eq!(
            verify_voucher_signed_message(&bytes, hash, &state, &program_id, &channel_account),
            Err(RuntimeAuthorityError::InvalidField(
                "cumulative_authorized_base_units"
            ))
        );
    }

    #[test]
    fn recomputed_hash_cannot_authorize_substituted_voucher_context() {
        let vector: Value = serde_json::from_str(VOUCHER_VECTOR).unwrap();
        let projection = &vector["parsed_projection"];
        let program_id = Pubkey::from_str(projection["program_id"].as_str().unwrap()).unwrap();
        let channel_account =
            Pubkey::from_str(projection["channel_account"].as_str().unwrap()).unwrap();
        let state = voucher_state(projection);

        let cases: Vec<(&'static str, Value, RuntimeAuthorityError)> = vec![
            (
                "network",
                Value::String("solana:mainnet".into()),
                RuntimeAuthorityError::ContextMismatch("network"),
            ),
            (
                "program_id",
                Value::String(Pubkey::new_from_array([41; 32]).to_string()),
                RuntimeAuthorityError::ContextMismatch("program_id"),
            ),
            (
                "channel_id",
                Value::String("channel_substituted".into()),
                RuntimeAuthorityError::ContextMismatch("channel_id"),
            ),
            (
                "channel_account",
                Value::String(Pubkey::new_from_array([42; 32]).to_string()),
                RuntimeAuthorityError::ContextMismatch("channel_account"),
            ),
            (
                "epoch",
                Value::from(1_u64),
                RuntimeAuthorityError::ContextMismatch("epoch"),
            ),
            (
                "sender",
                Value::String(Pubkey::new_from_array([43; 32]).to_string()),
                RuntimeAuthorityError::ContextMismatch("sender"),
            ),
            (
                "recipient_claim_pubkey",
                Value::String(Pubkey::new_from_array([44; 32]).to_string()),
                RuntimeAuthorityError::ContextMismatch("recipient_claim_pubkey"),
            ),
            (
                "mint",
                Value::String(Pubkey::new_from_array([45; 32]).to_string()),
                RuntimeAuthorityError::ContextMismatch("mint"),
            ),
            (
                "previous_activated_voucher_hash",
                Value::String(format!("sha256:{}", "00".repeat(32))),
                RuntimeAuthorityError::ContextMismatch("previous_activated_voucher_hash"),
            ),
        ];

        for (field, replacement, expected) in cases {
            let mut payload = projection.clone();
            payload[field] = replacement;
            let bytes = serde_json::to_vec(&payload).unwrap();
            assert_eq!(
                verify_voucher_signed_message(
                    &bytes,
                    sha256(&bytes),
                    &state,
                    &program_id,
                    &channel_account,
                ),
                Err(expected),
                "substitution unexpectedly survived for {field}"
            );
        }
    }

    fn voucher_state(projection: &Value) -> ChannelState {
        let genesis = Pubkey::from_str(projection["genesis_hash"].as_str().unwrap()).unwrap();
        let sender = Pubkey::from_str(projection["sender"].as_str().unwrap()).unwrap();
        let claim =
            Pubkey::from_str(projection["recipient_claim_pubkey"].as_str().unwrap()).unwrap();
        let mint = Pubkey::from_str(projection["mint"].as_str().unwrap()).unwrap();
        let previous = parse_sha256(
            projection["previous_activated_voucher_hash"].as_str().unwrap(),
        );
        ChannelState {
            account_version: CHANNEL_STATE_VERSION_V1,
            bump: 1,
            status: StatusCode::Active,
            environment: EnvironmentCode::DevnetFixture,
            network: NetworkCode::Solana,
            program_version: 1,
            policy_flags: 0,
            genesis_hash: genesis.to_bytes(),
            channel_nonce: [1; 32],
            channel_id_hash: channel_id_hash(projection["channel_id"].as_str().unwrap()).unwrap(),
            epoch: projection["epoch"].as_u64().unwrap(),
            sender,
            recipient_claim_pubkey: claim,
            recipient_wallet: Pubkey::default(),
            recipient_bound: 0,
            binding_nonce: encode_binding_nonce_u64(INITIAL_BINDING_NONCE),
            mint,
            vault_token_account: Pubkey::new_from_array([46; 32]),
            decimals: 6,
            funded_total: 100_000_000,
            activated_authorized_total: 25_000_000,
            settled_total: 0,
            refunded_total: 0,
            latest_activated_sequence: 2,
            latest_activated_voucher_hash: previous,
            channel_expiry_set: 0,
            channel_expiry: 0,
            voucher_expiry_set: 0,
            voucher_expiry: 0,
            close_requested: 0,
            close_requested_at: 0,
            claim_deadline_set: 0,
            claim_deadline: 0,
            reserved: [0; CHANNEL_STATE_RESERVED_BYTES],
        }
    }

    fn parse_sha256(value: &str) -> [u8; 32] {
        let encoded = value.strip_prefix("sha256:").unwrap();
        let mut output = [0_u8; 32];
        hex::decode_to_slice(encoded, &mut output).unwrap();
        output
    }

    fn sha256(bytes: &[u8]) -> [u8; 32] {
        Sha256::digest(bytes).into()
    }
}
