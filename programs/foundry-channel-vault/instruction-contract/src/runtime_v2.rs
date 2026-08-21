//! FC-SOL-003B runtime instruction profile and exact signed-authority binding.
//!
//! This module deliberately contains no Solana entrypoint, AccountInfo, CPI,
//! token transfer, RPC, signer custody, or deployment support. It closes the
//! transport/runtime operability gap while preserving the historical v1
//! instruction bytes and the 490-byte ChannelState layout.

use foundry_channel_vault_account_model::{ChannelState, EnvironmentCode};
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};
use solana_pubkey::Pubkey;
use std::{fmt, str::FromStr};

use crate::instruction::{instruction_discriminator, InstructionKind};

pub const INSTRUCTION_CONTRACT_VERSION_V2: u16 = 2;
pub const INITIAL_BINDING_NONCE: u64 = 1;
pub const INITIAL_LATEST_VOUCHER_HASH: [u8; 32] = [0; 32];
pub const JSON_SAFE_UNSIGNED_MAX: u64 = 9_007_199_254_740_991;

const VOUCHER_FIELDS: &[&str] = &[
    "domain",
    "protocol_version",
    "environment",
    "network",
    "genesis_hash",
    "program_id",
    "channel_id",
    "channel_account",
    "epoch",
    "sequence",
    "previous_activated_voucher_hash",
    "sender",
    "recipient_claim_pubkey",
    "mint",
    "cumulative_authorized_base_units",
    "issued_at",
    "expires_at",
];

const BINDING_FIELDS: &[&str] = &[
    "domain",
    "protocol_version",
    "environment",
    "network",
    "genesis_hash",
    "program_id",
    "channel_id",
    "channel_account",
    "epoch",
    "claim_id",
    "claim_pubkey",
    "voucher_hash",
    "mint",
    "binding_mode",
    "destination_wallet",
    "binding_nonce",
    "issued_at",
    "expires_at",
];

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum RuntimeInstructionV2 {
    InitializeChannel {
        channel_nonce: [u8; 32],
        recipient_claim_pubkey: Pubkey,
        decimals: u8,
        channel_expiry: i64,
        genesis_hash: [u8; 32],
        channel_id_hash: [u8; 32],
        environment: u8,
        policy_flags: u32,
        binding_nonce: u64,
    },
    FundChannel {
        amount: u64,
    },
    ActivateVoucher {
        voucher_hash: [u8; 32],
    },
    BindRecipient {
        binding_hash: [u8; 32],
    },
    Settle {
        amount: u64,
        obligation_hash: [u8; 32],
    },
    RequestClose {
        claim_deadline: i64,
    },
    RefundUnallocated {
        amount: u64,
        refund_request_hash: [u8; 32],
    },
    FinalizeClose {
        finalization_hash: [u8; 32],
    },
}

impl RuntimeInstructionV2 {
    pub fn kind(&self) -> InstructionKind {
        match self {
            Self::InitializeChannel { .. } => InstructionKind::InitializeChannel,
            Self::FundChannel { .. } => InstructionKind::FundChannel,
            Self::ActivateVoucher { .. } => InstructionKind::ActivateVoucher,
            Self::BindRecipient { .. } => InstructionKind::BindRecipient,
            Self::Settle { .. } => InstructionKind::Settle,
            Self::RequestClose { .. } => InstructionKind::RequestClose,
            Self::RefundUnallocated { .. } => InstructionKind::RefundUnallocated,
            Self::FinalizeClose { .. } => InstructionKind::FinalizeClose,
        }
    }

    pub fn encode(&self) -> Vec<u8> {
        let mut output = Vec::with_capacity(self.encoded_len());
        output.extend_from_slice(&instruction_discriminator(self.kind()));
        output.extend_from_slice(&INSTRUCTION_CONTRACT_VERSION_V2.to_le_bytes());
        match self {
            Self::InitializeChannel {
                channel_nonce,
                recipient_claim_pubkey,
                decimals,
                channel_expiry,
                genesis_hash,
                channel_id_hash,
                environment,
                policy_flags,
                binding_nonce,
            } => {
                output.extend_from_slice(channel_nonce);
                output.extend_from_slice(recipient_claim_pubkey.as_ref());
                output.push(*decimals);
                output.extend_from_slice(&channel_expiry.to_le_bytes());
                output.extend_from_slice(genesis_hash);
                output.extend_from_slice(channel_id_hash);
                output.push(*environment);
                output.extend_from_slice(&policy_flags.to_le_bytes());
                output.extend_from_slice(&binding_nonce.to_le_bytes());
            }
            Self::FundChannel { amount } => output.extend_from_slice(&amount.to_le_bytes()),
            Self::ActivateVoucher { voucher_hash } => output.extend_from_slice(voucher_hash),
            Self::BindRecipient { binding_hash } => output.extend_from_slice(binding_hash),
            Self::Settle {
                amount,
                obligation_hash,
            } => {
                output.extend_from_slice(&amount.to_le_bytes());
                output.extend_from_slice(obligation_hash);
            }
            Self::RequestClose { claim_deadline } => {
                output.extend_from_slice(&claim_deadline.to_le_bytes());
            }
            Self::RefundUnallocated {
                amount,
                refund_request_hash,
            } => {
                output.extend_from_slice(&amount.to_le_bytes());
                output.extend_from_slice(refund_request_hash);
            }
            Self::FinalizeClose { finalization_hash } => {
                output.extend_from_slice(finalization_hash);
            }
        }
        output
    }

    pub fn decode(input: &[u8]) -> Result<Self, RuntimeInstructionV2DecodeError> {
        if input.len() < 10 {
            return Err(RuntimeInstructionV2DecodeError::WrongLength);
        }
        let discriminator: [u8; 8] = input[..8]
            .try_into()
            .map_err(|_| RuntimeInstructionV2DecodeError::WrongLength)?;
        let version = u16::from_le_bytes([input[8], input[9]]);
        if version != INSTRUCTION_CONTRACT_VERSION_V2 {
            return Err(RuntimeInstructionV2DecodeError::UnsupportedVersion(version));
        }
        let kind = InstructionKind::ALL
            .into_iter()
            .find(|candidate| instruction_discriminator(*candidate) == discriminator)
            .ok_or(RuntimeInstructionV2DecodeError::UnknownDiscriminator)?;
        decode_v2_payload(kind, &input[10..])
    }

    fn encoded_len(&self) -> usize {
        10 + match self {
            Self::InitializeChannel { .. } => 150,
            Self::FundChannel { .. } => 8,
            Self::ActivateVoucher { .. } => 32,
            Self::BindRecipient { .. } => 32,
            Self::Settle { .. } => 40,
            Self::RequestClose { .. } => 8,
            Self::RefundUnallocated { .. } => 40,
            Self::FinalizeClose { .. } => 32,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum RuntimeInstructionV2DecodeError {
    WrongLength,
    UnknownDiscriminator,
    UnsupportedVersion(u16),
}

impl fmt::Display for RuntimeInstructionV2DecodeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{self:?}")
    }
}

impl std::error::Error for RuntimeInstructionV2DecodeError {}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum RuntimeAuthorityError {
    InvalidJson,
    NonCanonicalJson,
    WrongObjectShape,
    MissingField(&'static str),
    UnknownField,
    InvalidField(&'static str),
    ContextMismatch(&'static str),
    HashMismatch,
    UnsupportedEnvironment,
    BindingNonceEncoding,
}

impl fmt::Display for RuntimeAuthorityError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{self:?}")
    }
}

impl std::error::Error for RuntimeAuthorityError {}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct VerifiedVoucherAuthority {
    pub sequence: u64,
    pub cumulative_authorized: u64,
    pub voucher_hash: [u8; 32],
    pub expires_at: i64,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct VerifiedRecipientBindingAuthority {
    pub destination_wallet: Pubkey,
    pub binding_nonce: u64,
    pub binding_hash: [u8; 32],
    pub expires_at: i64,
}

pub fn channel_id_hash(channel_id: &str) -> Result<[u8; 32], RuntimeAuthorityError> {
    validate_identifier(channel_id, "channel_id")?;
    Ok(Sha256::digest(channel_id.as_bytes()).into())
}

pub fn encode_binding_nonce_u64(value: u64) -> [u8; 32] {
    let mut output = [0_u8; 32];
    output[..8].copy_from_slice(&value.to_le_bytes());
    output
}

pub fn decode_binding_nonce_u64(value: &[u8; 32]) -> Result<u64, RuntimeAuthorityError> {
    if value[8..].iter().any(|byte| *byte != 0) {
        return Err(RuntimeAuthorityError::BindingNonceEncoding);
    }
    Ok(u64::from_le_bytes(value[..8].try_into().expect("fixed eight bytes")))
}

pub fn verify_voucher_signed_message(
    message: &[u8],
    expected_voucher_hash: [u8; 32],
    state: &ChannelState,
    program_id: &Pubkey,
    channel_account: &Pubkey,
) -> Result<VerifiedVoucherAuthority, RuntimeAuthorityError> {
    if sha256(message) != expected_voucher_hash {
        return Err(RuntimeAuthorityError::HashMismatch);
    }
    let value = canonical_object(message, VOUCHER_FIELDS)?;
    let object = value
        .as_object()
        .expect("canonical_object already requires an object");

    expect_literal(object, "domain", "foundry.channels.voucher")?;
    verify_common_context(object, state, program_id, channel_account)?;
    expect_pubkey(object, "sender", &state.sender)?;
    expect_pubkey(
        object,
        "recipient_claim_pubkey",
        &state.recipient_claim_pubkey,
    )?;
    expect_pubkey(object, "mint", &state.mint)?;

    let sequence = safe_integer(object, "sequence")?;
    if sequence == 0 {
        return Err(RuntimeAuthorityError::InvalidField("sequence"));
    }
    let previous = hash_field(object, "previous_activated_voucher_hash")?;
    if previous != state.latest_activated_voucher_hash {
        return Err(RuntimeAuthorityError::ContextMismatch(
            "previous_activated_voucher_hash",
        ));
    }
    let cumulative_authorized = amount_field(object, "cumulative_authorized_base_units")?;
    let issued_at = timestamp_field(object, "issued_at")?;
    let expires_at = timestamp_field(object, "expires_at")?;
    if expires_at <= issued_at {
        return Err(RuntimeAuthorityError::InvalidField("expires_at"));
    }

    Ok(VerifiedVoucherAuthority {
        sequence,
        cumulative_authorized,
        voucher_hash: expected_voucher_hash,
        expires_at,
    })
}

pub fn verify_recipient_binding_signed_message(
    message: &[u8],
    expected_binding_hash: [u8; 32],
    expected_ed25519_destination: &Pubkey,
    state: &ChannelState,
    program_id: &Pubkey,
    channel_account: &Pubkey,
) -> Result<VerifiedRecipientBindingAuthority, RuntimeAuthorityError> {
    if sha256(message) != expected_binding_hash {
        return Err(RuntimeAuthorityError::HashMismatch);
    }
    let value = canonical_object(message, BINDING_FIELDS)?;
    let object = value
        .as_object()
        .expect("canonical_object already requires an object");

    expect_literal(
        object,
        "domain",
        "foundry.channels.recipient-binding",
    )?;
    verify_common_context(object, state, program_id, channel_account)?;
    validate_identifier(string_field(object, "claim_id")?, "claim_id")?;
    expect_pubkey(object, "claim_pubkey", &state.recipient_claim_pubkey)?;
    expect_pubkey(object, "mint", &state.mint)?;
    expect_literal(object, "binding_mode", "initial")?;

    let voucher_hash = hash_field(object, "voucher_hash")?;
    if voucher_hash != state.latest_activated_voucher_hash {
        return Err(RuntimeAuthorityError::ContextMismatch("voucher_hash"));
    }

    let destination_wallet = pubkey_field(object, "destination_wallet")?;
    if &destination_wallet != expected_ed25519_destination {
        return Err(RuntimeAuthorityError::ContextMismatch("destination_wallet"));
    }

    let binding_nonce = safe_integer(object, "binding_nonce")?;
    if binding_nonce == 0 || binding_nonce > JSON_SAFE_UNSIGNED_MAX {
        return Err(RuntimeAuthorityError::InvalidField("binding_nonce"));
    }
    if encode_binding_nonce_u64(binding_nonce) != state.binding_nonce {
        return Err(RuntimeAuthorityError::ContextMismatch("binding_nonce"));
    }

    let issued_at = timestamp_field(object, "issued_at")?;
    let expires_at = timestamp_field(object, "expires_at")?;
    if expires_at <= issued_at {
        return Err(RuntimeAuthorityError::InvalidField("expires_at"));
    }

    Ok(VerifiedRecipientBindingAuthority {
        destination_wallet,
        binding_nonce,
        binding_hash: expected_binding_hash,
        expires_at,
    })
}

fn decode_v2_payload(
    kind: InstructionKind,
    payload: &[u8],
) -> Result<RuntimeInstructionV2, RuntimeInstructionV2DecodeError> {
    let exact = |length: usize| {
        if payload.len() == length {
            Ok(())
        } else {
            Err(RuntimeInstructionV2DecodeError::WrongLength)
        }
    };
    match kind {
        InstructionKind::InitializeChannel => {
            exact(150)?;
            Ok(RuntimeInstructionV2::InitializeChannel {
                channel_nonce: payload[0..32].try_into().unwrap(),
                recipient_claim_pubkey: Pubkey::new_from_array(payload[32..64].try_into().unwrap()),
                decimals: payload[64],
                channel_expiry: i64::from_le_bytes(payload[65..73].try_into().unwrap()),
                genesis_hash: payload[73..105].try_into().unwrap(),
                channel_id_hash: payload[105..137].try_into().unwrap(),
                environment: payload[137],
                policy_flags: u32::from_le_bytes(payload[138..142].try_into().unwrap()),
                binding_nonce: u64::from_le_bytes(payload[142..150].try_into().unwrap()),
            })
        }
        InstructionKind::FundChannel => {
            exact(8)?;
            Ok(RuntimeInstructionV2::FundChannel {
                amount: u64::from_le_bytes(payload.try_into().unwrap()),
            })
        }
        InstructionKind::ActivateVoucher => {
            exact(32)?;
            Ok(RuntimeInstructionV2::ActivateVoucher {
                voucher_hash: payload.try_into().unwrap(),
            })
        }
        InstructionKind::BindRecipient => {
            exact(32)?;
            Ok(RuntimeInstructionV2::BindRecipient {
                binding_hash: payload.try_into().unwrap(),
            })
        }
        InstructionKind::Settle => {
            exact(40)?;
            Ok(RuntimeInstructionV2::Settle {
                amount: u64::from_le_bytes(payload[0..8].try_into().unwrap()),
                obligation_hash: payload[8..40].try_into().unwrap(),
            })
        }
        InstructionKind::RequestClose => {
            exact(8)?;
            Ok(RuntimeInstructionV2::RequestClose {
                claim_deadline: i64::from_le_bytes(payload.try_into().unwrap()),
            })
        }
        InstructionKind::RefundUnallocated => {
            exact(40)?;
            Ok(RuntimeInstructionV2::RefundUnallocated {
                amount: u64::from_le_bytes(payload[0..8].try_into().unwrap()),
                refund_request_hash: payload[8..40].try_into().unwrap(),
            })
        }
        InstructionKind::FinalizeClose => {
            exact(32)?;
            Ok(RuntimeInstructionV2::FinalizeClose {
                finalization_hash: payload.try_into().unwrap(),
            })
        }
    }
}

fn canonical_object(
    message: &[u8],
    required_fields: &[&'static str],
) -> Result<Value, RuntimeAuthorityError> {
    let value: Value = serde_json::from_slice(message).map_err(|_| RuntimeAuthorityError::InvalidJson)?;
    if !value.is_object() {
        return Err(RuntimeAuthorityError::WrongObjectShape);
    }
    let canonical = serde_json::to_vec(&value).map_err(|_| RuntimeAuthorityError::InvalidJson)?;
    if canonical.as_slice() != message {
        return Err(RuntimeAuthorityError::NonCanonicalJson);
    }
    let object = value.as_object().expect("object checked above");
    for field in required_fields {
        if !object.contains_key(*field) {
            return Err(RuntimeAuthorityError::MissingField(field));
        }
    }
    if object.len() != required_fields.len()
        || object
            .keys()
            .any(|field| !required_fields.contains(&field.as_str()))
    {
        return Err(RuntimeAuthorityError::UnknownField);
    }
    Ok(value)
}

fn verify_common_context(
    object: &Map<String, Value>,
    state: &ChannelState,
    program_id: &Pubkey,
    channel_account: &Pubkey,
) -> Result<(), RuntimeAuthorityError> {
    expect_literal(object, "protocol_version", "1.0.0")?;
    let environment = match state.environment {
        EnvironmentCode::DevnetFixture => "devnet",
        EnvironmentCode::LocalValidator => return Err(RuntimeAuthorityError::UnsupportedEnvironment),
    };
    expect_literal(object, "environment", environment)?;
    expect_literal(object, "network", "solana:devnet")?;

    let genesis_hash = pubkey_field(object, "genesis_hash")?;
    if genesis_hash.to_bytes() != state.genesis_hash {
        return Err(RuntimeAuthorityError::ContextMismatch("genesis_hash"));
    }
    expect_pubkey(object, "program_id", program_id)?;
    expect_pubkey(object, "channel_account", channel_account)?;

    let channel_id = string_field(object, "channel_id")?;
    if channel_id_hash(channel_id)? != state.channel_id_hash {
        return Err(RuntimeAuthorityError::ContextMismatch("channel_id"));
    }
    if safe_integer(object, "epoch")? != state.epoch {
        return Err(RuntimeAuthorityError::ContextMismatch("epoch"));
    }
    Ok(())
}

fn expect_literal(
    object: &Map<String, Value>,
    field: &'static str,
    expected: &str,
) -> Result<(), RuntimeAuthorityError> {
    if string_field(object, field)? != expected {
        return Err(RuntimeAuthorityError::ContextMismatch(field));
    }
    Ok(())
}

fn expect_pubkey(
    object: &Map<String, Value>,
    field: &'static str,
    expected: &Pubkey,
) -> Result<(), RuntimeAuthorityError> {
    if &pubkey_field(object, field)? != expected {
        return Err(RuntimeAuthorityError::ContextMismatch(field));
    }
    Ok(())
}

fn string_field<'a>(
    object: &'a Map<String, Value>,
    field: &'static str,
) -> Result<&'a str, RuntimeAuthorityError> {
    object
        .get(field)
        .and_then(Value::as_str)
        .ok_or(RuntimeAuthorityError::InvalidField(field))
}

fn safe_integer(
    object: &Map<String, Value>,
    field: &'static str,
) -> Result<u64, RuntimeAuthorityError> {
    let value = object
        .get(field)
        .and_then(Value::as_u64)
        .ok_or(RuntimeAuthorityError::InvalidField(field))?;
    if value > JSON_SAFE_UNSIGNED_MAX {
        return Err(RuntimeAuthorityError::InvalidField(field));
    }
    Ok(value)
}

fn pubkey_field(
    object: &Map<String, Value>,
    field: &'static str,
) -> Result<Pubkey, RuntimeAuthorityError> {
    Pubkey::from_str(string_field(object, field)?)
        .map_err(|_| RuntimeAuthorityError::InvalidField(field))
}

fn hash_field(
    object: &Map<String, Value>,
    field: &'static str,
) -> Result<[u8; 32], RuntimeAuthorityError> {
    parse_sha256_text(string_field(object, field)?, field)
}

fn parse_sha256_text(
    value: &str,
    field: &'static str,
) -> Result<[u8; 32], RuntimeAuthorityError> {
    let encoded = value
        .strip_prefix("sha256:")
        .ok_or(RuntimeAuthorityError::InvalidField(field))?;
    if encoded.len() != 64
        || !encoded
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(RuntimeAuthorityError::InvalidField(field));
    }
    let mut output = [0_u8; 32];
    hex::decode_to_slice(encoded, &mut output)
        .map_err(|_| RuntimeAuthorityError::InvalidField(field))?;
    Ok(output)
}

fn amount_field(
    object: &Map<String, Value>,
    field: &'static str,
) -> Result<u64, RuntimeAuthorityError> {
    let value = string_field(object, field)?;
    if value.is_empty()
        || (value.len() > 1 && value.starts_with('0'))
        || !value.bytes().all(|byte| byte.is_ascii_digit())
    {
        return Err(RuntimeAuthorityError::InvalidField(field));
    }
    value
        .parse::<u64>()
        .map_err(|_| RuntimeAuthorityError::InvalidField(field))
}

fn timestamp_field(
    object: &Map<String, Value>,
    field: &'static str,
) -> Result<i64, RuntimeAuthorityError> {
    parse_utc_timestamp(string_field(object, field)?, field)
}

fn parse_utc_timestamp(
    value: &str,
    field: &'static str,
) -> Result<i64, RuntimeAuthorityError> {
    let bytes = value.as_bytes();
    if bytes.len() != 20
        || bytes[4] != b'-'
        || bytes[7] != b'-'
        || bytes[10] != b'T'
        || bytes[13] != b':'
        || bytes[16] != b':'
        || bytes[19] != b'Z'
        || bytes.iter().enumerate().any(|(index, byte)| {
            !matches!(index, 4 | 7 | 10 | 13 | 16 | 19) && !byte.is_ascii_digit()
        })
    {
        return Err(RuntimeAuthorityError::InvalidField(field));
    }

    let year = decimal(bytes, 0, 4).ok_or(RuntimeAuthorityError::InvalidField(field))? as i64;
    let month = decimal(bytes, 5, 7).ok_or(RuntimeAuthorityError::InvalidField(field))?;
    let day = decimal(bytes, 8, 10).ok_or(RuntimeAuthorityError::InvalidField(field))?;
    let hour = decimal(bytes, 11, 13).ok_or(RuntimeAuthorityError::InvalidField(field))?;
    let minute = decimal(bytes, 14, 16).ok_or(RuntimeAuthorityError::InvalidField(field))?;
    let second = decimal(bytes, 17, 19).ok_or(RuntimeAuthorityError::InvalidField(field))?;

    if year < 1
        || !(1..=12).contains(&month)
        || day == 0
        || day > days_in_month(year, month)
        || hour > 23
        || minute > 59
        || second > 59
    {
        return Err(RuntimeAuthorityError::InvalidField(field));
    }

    let days = days_from_civil(year, month, day);
    days.checked_mul(86_400)
        .and_then(|value| value.checked_add(i64::from(hour) * 3_600))
        .and_then(|value| value.checked_add(i64::from(minute) * 60))
        .and_then(|value| value.checked_add(i64::from(second)))
        .ok_or(RuntimeAuthorityError::InvalidField(field))
}

fn decimal(bytes: &[u8], start: usize, end: usize) -> Option<u32> {
    let mut value = 0_u32;
    for byte in &bytes[start..end] {
        if !byte.is_ascii_digit() {
            return None;
        }
        value = value.checked_mul(10)?.checked_add(u32::from(*byte - b'0'))?;
    }
    Some(value)
}

fn days_in_month(year: i64, month: u32) -> u32 {
    match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if is_leap_year(year) => 29,
        2 => 28,
        _ => 0,
    }
}

fn is_leap_year(year: i64) -> bool {
    year % 4 == 0 && (year % 100 != 0 || year % 400 == 0)
}

fn days_from_civil(mut year: i64, month: u32, day: u32) -> i64 {
    if month <= 2 {
        year -= 1;
    }
    let era = if year >= 0 { year } else { year - 399 } / 400;
    let year_of_era = year - era * 400;
    let month_prime = i64::from(month) + if month > 2 { -3 } else { 9 };
    let day_of_year = (153 * month_prime + 2) / 5 + i64::from(day) - 1;
    let day_of_era = year_of_era * 365 + year_of_era / 4 - year_of_era / 100 + day_of_year;
    era * 146_097 + day_of_era - 719_468
}

fn validate_identifier(
    value: &str,
    field: &'static str,
) -> Result<(), RuntimeAuthorityError> {
    let bytes = value.as_bytes();
    if bytes.is_empty()
        || bytes.len() > 128
        || !bytes[0].is_ascii_alphanumeric()
        || !bytes.iter().all(|byte| {
            byte.is_ascii_alphanumeric() || matches!(*byte, b'.' | b'_' | b':' | b'-')
        })
    {
        return Err(RuntimeAuthorityError::InvalidField(field));
    }
    Ok(())
}

fn sha256(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ed25519::{
        build_binding_ed25519_data, build_voucher_ed25519_data,
        extract_binding_ed25519_message, extract_voucher_ed25519_message,
        ED25519_PROGRAM_ID_BYTES,
    };
    use foundry_channel_vault_account_model::{
        EnvironmentCode, NetworkCode, StatusCode, CHANNEL_STATE_RESERVED_BYTES,
        CHANNEL_STATE_VERSION_V1,
    };

    const VOUCHER_VECTOR: &str = include_str!(
        "../../../../contracts/channel/canonicalization/positive/voucher-payload-v1.json"
    );
    const BINDING_VECTOR: &str = include_str!(
        "../../../../contracts/channel/canonicalization/positive/recipient-binding-payload-v1.json"
    );

    fn instruction_fixtures() -> Vec<RuntimeInstructionV2> {
        vec![
            RuntimeInstructionV2::InitializeChannel {
                channel_nonce: [1; 32],
                recipient_claim_pubkey: Pubkey::new_from_array([2; 32]),
                decimals: 6,
                channel_expiry: 1_800_000_000,
                genesis_hash: [3; 32],
                channel_id_hash: [4; 32],
                environment: 1,
                policy_flags: 0b11,
                binding_nonce: 1,
            },
            RuntimeInstructionV2::FundChannel { amount: 100 },
            RuntimeInstructionV2::ActivateVoucher {
                voucher_hash: [5; 32],
            },
            RuntimeInstructionV2::BindRecipient {
                binding_hash: [6; 32],
            },
            RuntimeInstructionV2::Settle {
                amount: 25,
                obligation_hash: [7; 32],
            },
            RuntimeInstructionV2::RequestClose {
                claim_deadline: 1_700_086_400,
            },
            RuntimeInstructionV2::RefundUnallocated {
                amount: 60,
                refund_request_hash: [8; 32],
            },
            RuntimeInstructionV2::FinalizeClose {
                finalization_hash: [9; 32],
            },
        ]
    }

    #[test]
    fn runtime_v2_round_trips_all_eight_without_changing_discriminators() {
        for instruction in instruction_fixtures() {
            let encoded = instruction.encode();
            assert_eq!(&encoded[..8], &instruction_discriminator(instruction.kind()));
            assert_eq!(u16::from_le_bytes(encoded[8..10].try_into().unwrap()), 2);
            assert_eq!(RuntimeInstructionV2::decode(&encoded), Ok(instruction));
        }
    }

    #[test]
    fn runtime_v2_rejects_v1_and_trailing_bytes() {
        let mut encoded = RuntimeInstructionV2::FundChannel { amount: 1 }.encode();
        encoded[8..10].copy_from_slice(&1_u16.to_le_bytes());
        assert_eq!(
            RuntimeInstructionV2::decode(&encoded),
            Err(RuntimeInstructionV2DecodeError::UnsupportedVersion(1))
        );
        let mut trailing = RuntimeInstructionV2::ActivateVoucher {
            voucher_hash: [1; 32],
        }
        .encode();
        trailing.push(0);
        assert_eq!(
            RuntimeInstructionV2::decode(&trailing),
            Err(RuntimeInstructionV2DecodeError::WrongLength)
        );
    }

    #[test]
    fn channel_id_and_binding_nonce_mappings_are_deterministic() {
        assert_eq!(
            hex::encode(channel_id_hash("channel_foundations_001").unwrap()),
            "ceae0438987de294cc416407490c5b0b679651e8a96392799ff1ebf586881c5b"
        );
        let nonce = encode_binding_nonce_u64(INITIAL_BINDING_NONCE);
        assert_eq!(&nonce[..8], &1_u64.to_le_bytes());
        assert!(nonce[8..].iter().all(|byte| *byte == 0));
        assert_eq!(decode_binding_nonce_u64(&nonce), Ok(1));
        let mut poisoned = nonce;
        poisoned[31] = 1;
        assert_eq!(
            decode_binding_nonce_u64(&poisoned),
            Err(RuntimeAuthorityError::BindingNonceEncoding)
        );
        assert_eq!(INITIAL_LATEST_VOUCHER_HASH, [0; 32]);
    }

    #[test]
    fn exact_fc_proto_006_voucher_bytes_bind_all_runtime_authority() {
        let vector: Value = serde_json::from_str(VOUCHER_VECTOR).unwrap();
        let message = hex::decode(vector["canonical_utf8_hex"].as_str().unwrap()).unwrap();
        let expected_hash = parse_vector_hash(&vector);
        let projection = &vector["parsed_projection"];
        let program_id = Pubkey::from_str(projection["program_id"].as_str().unwrap()).unwrap();
        let channel_account =
            Pubkey::from_str(projection["channel_account"].as_str().unwrap()).unwrap();
        let state = voucher_state(projection);

        let verified = verify_voucher_signed_message(
            &message,
            expected_hash,
            &state,
            &program_id,
            &channel_account,
        )
        .unwrap();
        assert_eq!(verified.sequence, 3);
        assert_eq!(verified.cumulative_authorized, 40_000_000);
        assert_eq!(verified.voucher_hash, expected_hash);
        assert_eq!(verified.expires_at, 1_785_628_800);

        let precompile = build_voucher_ed25519_data(
            &state.sender.to_bytes(),
            &[7; 64],
            &message,
        )
        .unwrap();
        let extracted = extract_voucher_ed25519_message(
            &ED25519_PROGRAM_ID_BYTES,
            4,
            5,
            &precompile,
            &state.sender.to_bytes(),
        )
        .unwrap();
        assert_eq!(extracted, message.as_slice());
    }

    #[test]
    fn voucher_hash_and_context_substitution_fail_closed() {
        let vector: Value = serde_json::from_str(VOUCHER_VECTOR).unwrap();
        let message = hex::decode(vector["canonical_utf8_hex"].as_str().unwrap()).unwrap();
        let expected_hash = parse_vector_hash(&vector);
        let projection = &vector["parsed_projection"];
        let program_id = Pubkey::from_str(projection["program_id"].as_str().unwrap()).unwrap();
        let channel_account =
            Pubkey::from_str(projection["channel_account"].as_str().unwrap()).unwrap();
        let state = voucher_state(projection);

        let mut mutated: Value = serde_json::from_slice(&message).unwrap();
        mutated["cumulative_authorized_base_units"] = Value::String("40000001".into());
        let mutated_bytes = serde_json::to_vec(&mutated).unwrap();
        assert_eq!(
            verify_voucher_signed_message(
                &mutated_bytes,
                expected_hash,
                &state,
                &program_id,
                &channel_account,
            ),
            Err(RuntimeAuthorityError::HashMismatch)
        );

        mutated["cumulative_authorized_base_units"] = Value::String("40000000".into());
        mutated["mint"] = Value::String(Pubkey::new_from_array([42; 32]).to_string());
        let mutated_bytes = serde_json::to_vec(&mutated).unwrap();
        assert_eq!(
            verify_voucher_signed_message(
                &mutated_bytes,
                sha256(&mutated_bytes),
                &state,
                &program_id,
                &channel_account,
            ),
            Err(RuntimeAuthorityError::ContextMismatch("mint"))
        );

        let mut noncanonical = Vec::from(b" ".as_slice());
        noncanonical.extend_from_slice(&message);
        assert_eq!(
            verify_voucher_signed_message(
                &noncanonical,
                sha256(&noncanonical),
                &state,
                &program_id,
                &channel_account,
            ),
            Err(RuntimeAuthorityError::NonCanonicalJson)
        );
    }

    #[test]
    fn exact_fc_proto_006_binding_bytes_bind_both_ed25519_keys_and_state() {
        let vector: Value = serde_json::from_str(BINDING_VECTOR).unwrap();
        let message = hex::decode(vector["canonical_utf8_hex"].as_str().unwrap()).unwrap();
        let expected_hash = parse_vector_hash(&vector);
        let projection = &vector["parsed_projection"];
        let program_id = Pubkey::from_str(projection["program_id"].as_str().unwrap()).unwrap();
        let channel_account =
            Pubkey::from_str(projection["channel_account"].as_str().unwrap()).unwrap();
        let destination =
            Pubkey::from_str(projection["destination_wallet"].as_str().unwrap()).unwrap();
        let state = binding_state(projection);

        let verified = verify_recipient_binding_signed_message(
            &message,
            expected_hash,
            &destination,
            &state,
            &program_id,
            &channel_account,
        )
        .unwrap();
        assert_eq!(verified.destination_wallet, destination);
        assert_eq!(verified.binding_nonce, 1);
        assert_eq!(verified.binding_hash, expected_hash);
        assert_eq!(verified.expires_at, 1_785_543_000);

        let precompile = build_binding_ed25519_data(
            &state.recipient_claim_pubkey.to_bytes(),
            &[3; 64],
            &destination.to_bytes(),
            &[4; 64],
            &message,
        )
        .unwrap();
        let extracted = extract_binding_ed25519_message(
            &ED25519_PROGRAM_ID_BYTES,
            8,
            9,
            &precompile,
            &state.recipient_claim_pubkey.to_bytes(),
        )
        .unwrap();
        assert_eq!(extracted.destination_wallet, destination.to_bytes());
        assert_eq!(extracted.message, message.as_slice());
    }

    #[test]
    fn binding_destination_and_nonce_substitution_fail_closed() {
        let vector: Value = serde_json::from_str(BINDING_VECTOR).unwrap();
        let message = hex::decode(vector["canonical_utf8_hex"].as_str().unwrap()).unwrap();
        let projection = &vector["parsed_projection"];
        let program_id = Pubkey::from_str(projection["program_id"].as_str().unwrap()).unwrap();
        let channel_account =
            Pubkey::from_str(projection["channel_account"].as_str().unwrap()).unwrap();
        let destination =
            Pubkey::from_str(projection["destination_wallet"].as_str().unwrap()).unwrap();
        let state = binding_state(projection);

        let mut mutated: Value = serde_json::from_slice(&message).unwrap();
        mutated["destination_wallet"] =
            Value::String(Pubkey::new_from_array([43; 32]).to_string());
        let mutated_bytes = serde_json::to_vec(&mutated).unwrap();
        assert_eq!(
            verify_recipient_binding_signed_message(
                &mutated_bytes,
                sha256(&mutated_bytes),
                &destination,
                &state,
                &program_id,
                &channel_account,
            ),
            Err(RuntimeAuthorityError::ContextMismatch("destination_wallet"))
        );

        mutated["destination_wallet"] = Value::String(destination.to_string());
        mutated["binding_nonce"] = Value::from(2_u64);
        let mutated_bytes = serde_json::to_vec(&mutated).unwrap();
        assert_eq!(
            verify_recipient_binding_signed_message(
                &mutated_bytes,
                sha256(&mutated_bytes),
                &destination,
                &state,
                &program_id,
                &channel_account,
            ),
            Err(RuntimeAuthorityError::ContextMismatch("binding_nonce"))
        );
    }

    fn parse_vector_hash(vector: &Value) -> [u8; 32] {
        let text = vector["expected_sha256"].as_str().unwrap();
        parse_sha256_text(text, "vector_hash").unwrap()
    }

    fn voucher_state(projection: &Value) -> ChannelState {
        let genesis = Pubkey::from_str(projection["genesis_hash"].as_str().unwrap()).unwrap();
        let sender = Pubkey::from_str(projection["sender"].as_str().unwrap()).unwrap();
        let claim =
            Pubkey::from_str(projection["recipient_claim_pubkey"].as_str().unwrap()).unwrap();
        let mint = Pubkey::from_str(projection["mint"].as_str().unwrap()).unwrap();
        let previous = parse_sha256_text(
            projection["previous_activated_voucher_hash"].as_str().unwrap(),
            "previous_activated_voucher_hash",
        )
        .unwrap();
        base_state(
            genesis.to_bytes(),
            projection["channel_id"].as_str().unwrap(),
            projection["epoch"].as_u64().unwrap(),
            sender,
            claim,
            mint,
            previous,
        )
    }

    fn binding_state(projection: &Value) -> ChannelState {
        let genesis = Pubkey::from_str(projection["genesis_hash"].as_str().unwrap()).unwrap();
        let claim = Pubkey::from_str(projection["claim_pubkey"].as_str().unwrap()).unwrap();
        let mint = Pubkey::from_str(projection["mint"].as_str().unwrap()).unwrap();
        let voucher_hash =
            parse_sha256_text(projection["voucher_hash"].as_str().unwrap(), "voucher_hash")
                .unwrap();
        base_state(
            genesis.to_bytes(),
            projection["channel_id"].as_str().unwrap(),
            projection["epoch"].as_u64().unwrap(),
            Pubkey::new_from_array([44; 32]),
            claim,
            mint,
            voucher_hash,
        )
    }

    fn base_state(
        genesis_hash: [u8; 32],
        channel_id: &str,
        epoch: u64,
        sender: Pubkey,
        claim: Pubkey,
        mint: Pubkey,
        latest_hash: [u8; 32],
    ) -> ChannelState {
        ChannelState {
            account_version: CHANNEL_STATE_VERSION_V1,
            bump: 1,
            status: StatusCode::Active,
            environment: EnvironmentCode::DevnetFixture,
            network: NetworkCode::Solana,
            program_version: 1,
            policy_flags: 0,
            genesis_hash,
            channel_nonce: [1; 32],
            channel_id_hash: channel_id_hash(channel_id).unwrap(),
            epoch,
            sender,
            recipient_claim_pubkey: claim,
            recipient_wallet: Pubkey::default(),
            recipient_bound: 0,
            binding_nonce: encode_binding_nonce_u64(INITIAL_BINDING_NONCE),
            mint,
            vault_token_account: Pubkey::new_from_array([45; 32]),
            decimals: 6,
            funded_total: 100_000_000,
            activated_authorized_total: 25_000_000,
            settled_total: 0,
            refunded_total: 0,
            latest_activated_sequence: 2,
            latest_activated_voucher_hash: latest_hash,
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
}
