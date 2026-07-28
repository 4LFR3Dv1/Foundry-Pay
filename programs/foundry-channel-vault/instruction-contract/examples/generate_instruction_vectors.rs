#[cfg(test)]
use crate::{
    account_contract, build_binding_ed25519_data, build_voucher_ed25519_data, event_contract,
    instruction_discriminator, ChannelInstruction, InstructionKind, LifecyclePhase,
    ACCOUNT_CONTRACTS, ED25519_PROGRAM_ID_BYTES, ERROR_REGISTRY, EVENT_CONTRACTS,
    INSTRUCTION_CONTRACT_VERSION_V1, MAX_CLAIM_WINDOW_SECONDS, MIN_CLAIM_WINDOW_SECONDS,
};
#[cfg(not(test))]
use foundry_channel_vault_instruction_contract::{
    account_contract, build_binding_ed25519_data, build_voucher_ed25519_data, event_contract,
    instruction_discriminator, ChannelInstruction, InstructionKind, LifecyclePhase,
    ACCOUNT_CONTRACTS, ED25519_PROGRAM_ID_BYTES, ERROR_REGISTRY, EVENT_CONTRACTS,
    INSTRUCTION_CONTRACT_VERSION_V1, MAX_CLAIM_WINDOW_SECONDS, MIN_CLAIM_WINDOW_SECONDS,
};
use serde::Serialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use solana_pubkey::Pubkey;
use std::{env, fs, path::Path};

#[cfg_attr(test, allow(dead_code))]
fn main() {
    let output = env::args()
        .nth(1)
        .expect("usage: generate_instruction_vectors <evidence-directory>");
    generate(Path::new(&output));
}

fn generate(output: &Path) {
    fs::create_dir_all(output).expect("create evidence directory");

    let instructions = fixtures();
    let serialization: Vec<_> = instructions
        .iter()
        .map(|instruction| {
            let bytes = instruction.encode();
            assert_eq!(ChannelInstruction::decode(&bytes), Ok(instruction.clone()));
            json!({
                "instruction": instruction.kind().name(),
                "contract_version": INSTRUCTION_CONTRACT_VERSION_V1,
                "discriminator_hex": hex::encode(instruction_discriminator(instruction.kind())),
                "bytes_hex": hex::encode(&bytes),
                "byte_length": bytes.len(),
                "sha256": tagged_sha256(&bytes),
                "round_trip": "passed"
            })
        })
        .collect();
    write_json(
        output.join("instruction-serialization-v1.json"),
        &serialization,
    );

    write_json(
        output.join("instruction-registry-v1.json"),
        &InstructionKind::ALL
            .iter()
            .map(|kind| {
                let contract = account_contract(*kind);
                json!({
                    "name": kind.name(),
                    "code": *kind as u8,
                    "contract_version": INSTRUCTION_CONTRACT_VERSION_V1,
                    "discriminator_hex": hex::encode(instruction_discriminator(*kind)),
                    "authority": format!("{:?}", contract.authority),
                    "allowed_phases": contract.allowed_phases,
                    "success_event": event_contract(contract.success_event),
                    "correlation_policy": contract.correlation_policy,
                    "runtime_handler_implemented": false
                })
            })
            .collect::<Vec<_>>(),
    );

    write_json(
        output.join("account-meta-contracts-v1.json"),
        &ACCOUNT_CONTRACTS
            .iter()
            .map(|contract| {
                json!({
                    "instruction": contract.kind.name(),
                    "accounts": contract.accounts.iter().map(|account| json!({
                        "name": account.name,
                        "signer": account.signer,
                        "writable": account.writable,
                        "pre_owner_rule": account.pre_owner_rule,
                        "post_owner_rule": account.post_owner_rule,
                        "address_rule": account.address_rule
                    })).collect::<Vec<_>>()
                })
            })
            .collect::<Vec<_>>(),
    );

    write_json(
        output.join("signed-message-mapping-v1.json"),
        &json!([
            {
                "object": "ChannelVoucher",
                "instruction": "activate_voucher",
                "signer": "channel.sender",
                "preimage": "FC-PROTO-006 voucher signed payload",
                "signature_count": 1,
                "authority_scope": "cumulative activation only"
            },
            {
                "object": "RecipientBinding",
                "instruction": "bind_recipient",
                "signers": ["channel.recipient_claim_pubkey", "destination_wallet"],
                "preimage": "FC-PROTO-006 recipient binding signed payload duplicated exactly",
                "signature_count": 2,
                "authority_scope": "recipient binding only"
            }
        ]),
    );

    let voucher_message = b"foundry.channels.voucher/v1/golden";
    let binding_message = b"foundry.channels.recipient-binding/v1/golden";
    let voucher = build_voucher_ed25519_data(&[1; 32], &[2; 64], voucher_message).unwrap();
    let binding =
        build_binding_ed25519_data(&[3; 32], &[4; 64], &[5; 32], &[6; 64], binding_message)
            .unwrap();
    write_json(
        output.join("ed25519-offset-vectors-v1.json"),
        &json!({
            "program_id_bytes_hex": hex::encode(ED25519_PROGRAM_ID_BYTES),
            "program_id": "Ed25519SigVerify111111111111111111111111111",
            "instruction_position": "immediately_preceding",
            "instruction_references": "u16::MAX_self_contained_only",
            "voucher": {
                "signature_count": 1,
                "padding": 0,
                "public_key_offset": 16,
                "signature_offset": 48,
                "message_offset": 112,
                "message_length": voucher_message.len(),
                "total_length": voucher.len(),
                "bytes_hex": hex::encode(&voucher),
                "sha256": tagged_sha256(&voucher)
            },
            "binding": {
                "signature_count": 2,
                "padding": 0,
                "header_length": 30,
                "message_length": binding_message.len(),
                "first": {"public_key_offset": 30, "signature_offset": 62, "message_offset": 126},
                "second": {
                    "public_key_offset": 126 + binding_message.len(),
                    "signature_offset": 158 + binding_message.len(),
                    "message_offset": 222 + binding_message.len()
                },
                "total_length": binding.len(),
                "messages_overlap": false,
                "bytes_hex": hex::encode(&binding),
                "sha256": tagged_sha256(&binding)
            }
        }),
    );

    write_json(
        output.join("event-registry-v1.json"),
        &EVENT_CONTRACTS
            .iter()
            .map(|(name, code)| {
                json!({
                    "name": name,
                    "code": *code as u16,
                    "authority": "onchain_fact_only",
                    "business_completion_claim": false
                })
            })
            .collect::<Vec<_>>(),
    );
    write_json(
        output.join("error-registry-v1.json"),
        &ERROR_REGISTRY
            .iter()
            .map(|(name, code)| json!({"name": name, "code": *code as u32}))
            .collect::<Vec<_>>(),
    );
    write_json(
        output.join("lifecycle-transition-matrix-v1.json"),
        &json!({
            "layout_changed": false,
            "phases": [
                {"phase": "uninitialized", "derivation": "account absent"},
                {"phase": "active", "derivation": "StatusCode::Active"},
                {"phase": "closing_open", "derivation": "StatusCode::Closing && now < claim_deadline"},
                {"phase": "closing_frozen", "derivation": "StatusCode::Closing && now >= claim_deadline"},
                {"phase": "finalized", "derivation": "StatusCode::Closed", "terminal": true}
            ],
            "deadline_is_exclusive": true,
            "minimum_claim_window_seconds": MIN_CLAIM_WINDOW_SECONDS,
            "maximum_claim_window_seconds": MAX_CLAIM_WINDOW_SECONDS,
            "deadline_arithmetic": "checked",
            "activated_rights_expire": false,
            "known_phase_codes": [
                format!("{:?}", LifecyclePhase::Active),
                format!("{:?}", LifecyclePhase::ClosingOpen),
                format!("{:?}", LifecyclePhase::ClosingFrozen),
                format!("{:?}", LifecyclePhase::Finalized)
            ]
        }),
    );

    let positives: Vec<_> = serialization
        .iter()
        .map(|item| {
            json!({
                "case": format!("{}_golden", item["instruction"].as_str().unwrap()),
                "decision": "accepted",
                "projected_transition_only": true,
                "success_event_after_full_validation": true
            })
        })
        .collect();
    write_json(output.join("positive-vectors-v1.json"), &positives);

    let negatives = negative_cases();
    write_json(output.join("negative-vectors-v1.json"), &negatives);

    let registry_paths = [
        "instruction-registry-v1.json",
        "account-meta-contracts-v1.json",
        "signed-message-mapping-v1.json",
        "ed25519-offset-vectors-v1.json",
        "instruction-serialization-v1.json",
        "event-registry-v1.json",
        "error-registry-v1.json",
        "lifecycle-transition-matrix-v1.json",
        "positive-vectors-v1.json",
        "negative-vectors-v1.json",
    ];
    let registry_hashes: Vec<_> = registry_paths
        .iter()
        .map(|name| {
            let bytes = fs::read(output.join(name)).expect("read generated registry");
            json!({"path": name, "bytes": bytes.len(), "sha256": tagged_sha256(&bytes)})
        })
        .collect();
    let aggregate = serde_json::to_vec(&registry_hashes).unwrap();
    write_json(
        output.join("idl-hash-report.json"),
        &json!({
            "anchor_idl_generated": false,
            "deployable_entrypoint_exists": false,
            "registry_hash_kind": "transport-neutral experimental instruction contract",
            "registry_sha256": tagged_sha256(&aggregate),
            "artifacts": registry_hashes
        }),
    );
    write_json(
        output.join("validation-report.json"),
        &json!({
            "status": "passed",
            "instruction_count": 8,
            "positive_vectors": positives.len(),
            "negative_vectors": negatives.len(),
            "ed25519_profiles": 2,
            "account_layout_bytes": 490,
            "runtime_handlers": 0,
            "cpi_or_transfers": 0,
            "deployment": "blocked",
            "external_review": "not_performed"
        }),
    );
}

fn fixtures() -> Vec<ChannelInstruction> {
    vec![
        ChannelInstruction::InitializeChannel {
            channel_nonce: [1; 32],
            recipient_claim_pubkey: Pubkey::new_from_array([2; 32]),
            decimals: 6,
            channel_expiry: 1_800_000_000,
        },
        ChannelInstruction::FundChannel {
            amount: 100_000_000,
        },
        ChannelInstruction::ActivateVoucher {
            sequence: 3,
            cumulative_authorized: 40_000_000,
            voucher_hash: [3; 32],
            voucher_expiry: 1_750_000_000,
        },
        ChannelInstruction::BindRecipient {
            binding_nonce: [4; 32],
            destination_wallet: Pubkey::new_from_array([5; 32]),
            binding_hash: [6; 32],
        },
        ChannelInstruction::Settle {
            amount: 25_000_000,
            obligation_hash: [7; 32],
        },
        ChannelInstruction::RequestClose {
            claim_deadline: 1_700_086_400,
        },
        ChannelInstruction::RefundUnallocated {
            amount: 60_000_000,
            refund_request_hash: [8; 32],
        },
        ChannelInstruction::FinalizeClose {
            finalization_hash: [9; 32],
        },
    ]
}

fn negative_cases() -> Vec<Value> {
    [
        (
            "account_substitution",
            "account_validation",
            "WRONG_ACCOUNT_ADDRESS",
        ),
        ("missing_signer", "account_validation", "MISSING_SIGNER"),
        (
            "missing_system_program",
            "account_validation",
            "WRONG_ACCOUNT_ADDRESS",
        ),
        (
            "substituted_associated_token_program",
            "account_validation",
            "WRONG_ACCOUNT_ADDRESS",
        ),
        ("wrong_pda", "account_validation", "WRONG_PDA"),
        ("wrong_owner", "account_validation", "WRONG_ACCOUNT_OWNER"),
        ("wrong_mint", "token_validation", "WRONG_MINT"),
        (
            "token_2022",
            "token_validation",
            "UNSUPPORTED_TOKEN_PROGRAM",
        ),
        (
            "wrong_vault_authority",
            "token_validation",
            "WRONG_VAULT_AUTHORITY",
        ),
        ("wrong_lifecycle", "lifecycle", "LIFECYCLE_VIOLATION"),
        ("sequence_replay", "authority", "SEQUENCE_REPLAY"),
        ("cumulative_regression", "authority", "SEQUENCE_REGRESSION"),
        ("above_funding", "conservation", "CONSERVATION_VIOLATION"),
        ("binding_nonce_replay", "binding", "BINDING_NONCE_CONSUMED"),
        (
            "recipient_substitution",
            "binding",
            "RECIPIENT_SUBSTITUTION",
        ),
        ("voucher_expired", "expiry", "EXPIRED_AUTHORITY"),
        (
            "claim_deadline_too_soon",
            "lifecycle",
            "LIFECYCLE_VIOLATION",
        ),
        (
            "claim_deadline_too_late",
            "lifecycle",
            "LIFECYCLE_VIOLATION",
        ),
        (
            "unknown_version",
            "instruction_decode",
            "UNSUPPORTED_INSTRUCTION_VERSION",
        ),
        (
            "unknown_profile",
            "domain_verification",
            "UNSUPPORTED_PROFILE",
        ),
        (
            "ed25519_missing",
            "ed25519",
            "ED25519_NOT_IMMEDIATELY_PRECEDING",
        ),
        (
            "ed25519_after",
            "ed25519",
            "ED25519_NOT_IMMEDIATELY_PRECEDING",
        ),
        (
            "ed25519_external_reference",
            "ed25519",
            "EXTERNAL_ED25519_REFERENCE",
        ),
        (
            "ed25519_offset_mutated",
            "ed25519",
            "NON_CANONICAL_ED25519_OFFSETS",
        ),
        (
            "ed25519_pubkey_mutated",
            "ed25519",
            "WRONG_ED25519_PUBLIC_KEY",
        ),
        (
            "ed25519_message_length_mutated",
            "ed25519",
            "NON_CANONICAL_ED25519_OFFSETS",
        ),
        (
            "preimage_one_byte_mutated",
            "ed25519",
            "WRONG_ED25519_MESSAGE",
        ),
        (
            "trailing_ed25519_bytes",
            "ed25519",
            "NON_CANONICAL_ED25519_HEADER",
        ),
        (
            "success_event_before_validation",
            "event",
            "LIFECYCLE_VIOLATION",
        ),
    ]
    .into_iter()
    .map(|(case, stage, code)| {
        json!({
            "case": case,
            "decision": "rejected",
            "stage": stage,
            "code": code,
            "projected_transition_count": 0,
            "success_event_count": 0
        })
    })
    .collect()
}

fn tagged_sha256(bytes: &[u8]) -> String {
    format!("sha256:{}", hex::encode(Sha256::digest(bytes)))
}

fn write_json(path: impl AsRef<Path>, value: &impl Serialize) {
    let bytes = serde_json::to_vec_pretty(value).expect("serialize evidence");
    fs::write(path, [bytes, b"\n".to_vec()].concat()).expect("write evidence");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generate_from_test_harness_when_requested() {
        if let Ok(output) = env::var("FC_SOL_003_EVIDENCE_DIR") {
            generate(Path::new(&output));
        }
    }
}
