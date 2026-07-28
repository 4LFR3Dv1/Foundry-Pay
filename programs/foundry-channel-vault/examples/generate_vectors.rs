use base64::{engine::general_purpose::STANDARD as BASE64, Engine};
use foundry_channel_vault_account_model::{
    classic_token_program_id, derive_channel_pda, derive_vault_address, token_2022_program_id,
    validate_vault_account, ChannelState, EnvironmentCode, NetworkCode, StatusCode,
    VaultAccountView, CHANNEL_STATE_FIELDS, CHANNEL_STATE_RESERVED_BYTES, CHANNEL_STATE_SPACE,
    CHANNEL_STATE_VERSION_V1,
};
use serde::Serialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use solana_pubkey::Pubkey;
use solana_rent::Rent;
use std::{env, fs, path::Path};

#[derive(Serialize)]
struct PdaVector {
    vector_id: String,
    program_id: String,
    sender: String,
    mint: String,
    channel_nonce_hex: String,
    expected_pda: String,
    expected_bump: u8,
}

fn main() {
    let output = env::args()
        .nth(1)
        .expect("usage: generate_vectors <evidence-directory>");
    let output = Path::new(&output);
    fs::create_dir_all(output).expect("create evidence directory");

    let program_id = Pubkey::new_from_array([9; 32]);
    let sender = Pubkey::new_from_array([4; 32]);
    let mint = Pubkey::new_from_array([7; 32]);
    let base_nonce = [2; 32];

    let pda_inputs = [
        ("base", sender, mint, base_nonce),
        (
            "sender-mutated",
            Pubkey::new_from_array([14; 32]),
            mint,
            base_nonce,
        ),
        (
            "mint-mutated",
            sender,
            Pubkey::new_from_array([15; 32]),
            base_nonce,
        ),
        ("nonce-mutated", sender, mint, [16; 32]),
    ];
    let pda_vectors: Vec<_> = pda_inputs
        .iter()
        .map(|(id, vector_sender, vector_mint, nonce)| {
            let (pda, bump) = derive_channel_pda(&program_id, vector_sender, vector_mint, nonce);
            PdaVector {
                vector_id: (*id).to_owned(),
                program_id: program_id.to_string(),
                sender: vector_sender.to_string(),
                mint: vector_mint.to_string(),
                channel_nonce_hex: hex::encode(nonce),
                expected_pda: pda.to_string(),
                expected_bump: bump,
            }
        })
        .collect();
    write_json(output.join("pda-vectors-v1.json"), &pda_vectors);

    let layout: Vec<_> = CHANNEL_STATE_FIELDS
        .iter()
        .map(|(name, offset, width)| {
            json!({"field": name, "offset": offset, "width": width, "end_exclusive": offset + width})
        })
        .collect();
    write_json(
        output.join("account-layout-v1.json"),
        &json!({
            "account": "ChannelState",
            "account_version": CHANNEL_STATE_VERSION_V1,
            "encoding": "fixed-width little-endian",
            "discriminator_rule": "sha256(account:ChannelState)[0:8]",
            "space": CHANNEL_STATE_SPACE,
            "reserved_bytes": CHANNEL_STATE_RESERVED_BYTES,
            "variable_width_fields": false,
            "fields": layout
        }),
    );
    write_json(
        output.join("account-field-offsets-v1.json"),
        &json!({
            "space": CHANNEL_STATE_SPACE,
            "contiguous": true,
            "fields": layout
        }),
    );

    let (channel_pda, bump) = derive_channel_pda(&program_id, &sender, &mint, &base_nonce);
    let vault = derive_vault_address(&channel_pda, &mint);
    let vectors = [
        ("zero-initialized", zero_state(sender, mint, vault, bump)),
        ("funded-active", active_state(sender, mint, vault, bump)),
        ("closing-bound", closing_state(sender, mint, vault, bump)),
    ];
    let serialized: Vec<_> = vectors
        .iter()
        .map(|(id, state)| {
            let bytes = state.serialize().expect("valid golden state");
            let decoded = ChannelState::deserialize(&bytes).expect("golden round trip");
            assert_eq!(*state, decoded);
            json!({
                "vector_id": id,
                "byte_length": bytes.len(),
                "bytes_hex": hex::encode(bytes),
                "bytes_base64": BASE64.encode(bytes),
                "sha256": format!("sha256:{}", hex::encode(Sha256::digest(bytes))),
                "decoded": state_json(state)
            })
        })
        .collect();
    write_json(
        output.join("serialized-golden-vectors-v1.json"),
        &serialized,
    );

    write_json(
        output.join("malformed-account-matrix.json"),
        &json!([
            {"case": "wrong_program_owner", "expected": "WrongProgramOwner"},
            {"case": "wrong_discriminator", "expected": "WrongDiscriminator"},
            {"case": "unknown_version", "expected": "UnknownVersion"},
            {"case": "short_length", "expected": "WrongLength"},
            {"case": "long_length", "expected": "WrongLength"},
            {"case": "unknown_status", "expected": "UnknownStatus"},
            {"case": "unknown_environment", "expected": "UnknownEnvironment"},
            {"case": "unknown_network", "expected": "UnknownNetwork"},
            {"case": "unknown_policy_flag", "expected": "UnknownPolicyFlags"},
            {"case": "invalid_boolean", "expected": "InvalidBoolean"},
            {"case": "recipient_binding_mismatch", "expected": "RecipientBindingMismatch"},
            {"case": "flag_value_mismatch", "expected": "FlagValueMismatch"},
            {"case": "reserved_nonzero", "expected": "ReservedBytesNonZero"}
        ]),
    );

    let state = active_state(sender, mint, vault, bump);
    let valid_view = VaultAccountView {
        address: vault,
        owner_program: classic_token_program_id(),
        mint,
        authority: channel_pda,
        token_program: classic_token_program_id(),
    };
    let token_cases = [
        (
            "exact-classic-vault",
            valid_view.clone(),
            validate_vault_account(&state, &channel_pda, &program_id, &valid_view),
        ),
        (
            "token-2022-owner",
            VaultAccountView {
                owner_program: token_2022_program_id(),
                ..valid_view.clone()
            },
            Err(foundry_channel_vault_account_model::VaultAccountError::WrongOwnerProgram),
        ),
        (
            "wrong-mint",
            VaultAccountView {
                mint: Pubkey::new_from_array([33; 32]),
                ..valid_view.clone()
            },
            Err(foundry_channel_vault_account_model::VaultAccountError::WrongMint),
        ),
        (
            "wrong-authority",
            VaultAccountView {
                authority: Pubkey::new_from_array([34; 32]),
                ..valid_view.clone()
            },
            Err(foundry_channel_vault_account_model::VaultAccountError::WrongAuthority),
        ),
    ];
    write_json(
        output.join("token-account-authority-report.json"),
        &token_cases
            .iter()
            .map(|(id, view, result)| {
                let actual = validate_vault_account(&state, &channel_pda, &program_id, view);
                assert_eq!(&actual, result);
                json!({
                    "case": id,
                    "decision": if actual.is_ok() { "accepted" } else { "rejected" },
                    "result": format!("{actual:?}")
                })
            })
            .collect::<Vec<_>>(),
    );

    let rent = Rent::default();
    write_json(
        output.join("rent-space-report.json"),
        &json!({
            "normative": {
                "channel_state_space": CHANNEL_STATE_SPACE
            },
            "environmental": {
                "model": "solana_rent::Rent::default()",
                "minimum_balance_lamports": rent.minimum_balance(CHANNEL_STATE_SPACE),
                "lamports_are_not_a_protocol_constant": true
            }
        }),
    );
}

fn zero_state(sender: Pubkey, mint: Pubkey, vault: Pubkey, bump: u8) -> ChannelState {
    ChannelState {
        account_version: CHANNEL_STATE_VERSION_V1,
        bump,
        status: StatusCode::Draft,
        environment: EnvironmentCode::LocalValidator,
        network: NetworkCode::Solana,
        program_version: 1,
        policy_flags: 0,
        genesis_hash: [1; 32],
        channel_nonce: [2; 32],
        channel_id_hash: [3; 32],
        epoch: 0,
        sender,
        recipient_claim_pubkey: Pubkey::new_from_array([5; 32]),
        recipient_wallet: Pubkey::default(),
        recipient_bound: 0,
        binding_nonce: [6; 32],
        mint,
        vault_token_account: vault,
        decimals: 6,
        funded_total: 0,
        activated_authorized_total: 0,
        settled_total: 0,
        refunded_total: 0,
        latest_activated_sequence: 0,
        latest_activated_voucher_hash: [0; 32],
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

fn active_state(sender: Pubkey, mint: Pubkey, vault: Pubkey, bump: u8) -> ChannelState {
    ChannelState {
        status: StatusCode::Active,
        policy_flags: 0b11,
        funded_total: 100_000_000,
        activated_authorized_total: 40_000_000,
        settled_total: 15_000_000,
        latest_activated_sequence: 3,
        latest_activated_voucher_hash: [10; 32],
        ..zero_state(sender, mint, vault, bump)
    }
}

fn closing_state(sender: Pubkey, mint: Pubkey, vault: Pubkey, bump: u8) -> ChannelState {
    ChannelState {
        status: StatusCode::Closing,
        recipient_wallet: Pubkey::new_from_array([11; 32]),
        recipient_bound: 1,
        channel_expiry_set: 1,
        channel_expiry: 1_800_000_000,
        voucher_expiry_set: 1,
        voucher_expiry: 1_750_000_000,
        close_requested: 1,
        close_requested_at: 1_700_000_000,
        claim_deadline_set: 1,
        claim_deadline: 1_700_086_400,
        ..active_state(sender, mint, vault, bump)
    }
}

fn state_json(state: &ChannelState) -> Value {
    json!({
        "account_version": state.account_version,
        "bump": state.bump,
        "status": state.status as u8,
        "environment": state.environment as u8,
        "network": state.network as u8,
        "program_version": state.program_version,
        "policy_flags": state.policy_flags,
        "genesis_hash_hex": hex::encode(state.genesis_hash),
        "channel_nonce_hex": hex::encode(state.channel_nonce),
        "channel_id_hash_hex": hex::encode(state.channel_id_hash),
        "epoch": state.epoch.to_string(),
        "sender": state.sender.to_string(),
        "recipient_claim_pubkey": state.recipient_claim_pubkey.to_string(),
        "recipient_wallet": state.recipient_wallet.to_string(),
        "recipient_bound": state.recipient_bound,
        "binding_nonce_hex": hex::encode(state.binding_nonce),
        "mint": state.mint.to_string(),
        "vault_account_public_key": state.vault_token_account.to_string(),
        "decimals": state.decimals,
        "funded_total": state.funded_total.to_string(),
        "activated_authorized_total": state.activated_authorized_total.to_string(),
        "settled_total": state.settled_total.to_string(),
        "refunded_total": state.refunded_total.to_string(),
        "latest_activated_sequence": state.latest_activated_sequence.to_string(),
        "latest_activated_voucher_hash_hex": hex::encode(state.latest_activated_voucher_hash),
        "channel_expiry_set": state.channel_expiry_set,
        "channel_expiry": state.channel_expiry,
        "voucher_expiry_set": state.voucher_expiry_set,
        "voucher_expiry": state.voucher_expiry,
        "close_requested": state.close_requested,
        "close_requested_at": state.close_requested_at,
        "claim_deadline_set": state.claim_deadline_set,
        "claim_deadline": state.claim_deadline,
        "reserved_hex": hex::encode(state.reserved)
    })
}

fn write_json(path: impl AsRef<Path>, value: &impl Serialize) {
    let bytes = serde_json::to_vec_pretty(value).expect("serialize evidence");
    fs::write(path, [bytes, b"\n".to_vec()].concat()).expect("write evidence");
}
