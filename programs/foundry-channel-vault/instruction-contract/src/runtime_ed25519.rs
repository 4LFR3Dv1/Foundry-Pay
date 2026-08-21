//! Runtime-only Ed25519 binding transport for FC-SOL-006.
//!
//! Historical FC-SOL-003/003B fixtures duplicate the exact recipient-binding
//! message once per signature. A canonical 780-byte binding therefore produces
//! 1,782 bytes of Ed25519 instruction data and cannot fit in the 1,232-byte
//! legacy/v0 Solana transaction envelope. This module preserves both signatures,
//! the exact signed bytes, self-contained references, ordering, and immediate
//! precompile position while allowing both signature records to reference one
//! shared in-instruction message range.
//!
//! The historical builder/verifier/extractor in `ed25519.rs` are intentionally
//! unchanged and remain the byte-reproducible v1 fixture surface.

use crate::ed25519::{Ed25519ContractError, ExtractedBindingMessage, ED25519_PROGRAM_ID_BYTES};

const OFFSETS_SIZE: usize = 14;
const CURRENT_INSTRUCTION: u16 = u16::MAX;
const BINDING_HEADER: usize = 30;
const FIRST_PUBLIC_KEY_OFFSET: usize = 30;
const FIRST_SIGNATURE_OFFSET: usize = 62;
const SECOND_PUBLIC_KEY_OFFSET: usize = 126;
const SECOND_SIGNATURE_OFFSET: usize = 158;
const SHARED_MESSAGE_OFFSET: usize = 222;

pub fn build_runtime_binding_ed25519_data(
    claim_key: &[u8; 32],
    claim_signature: &[u8; 64],
    destination_wallet: &[u8; 32],
    destination_signature: &[u8; 64],
    message: &[u8],
) -> Result<Vec<u8>, Ed25519ContractError> {
    ensure_u16(message.len())?;
    let total = SHARED_MESSAGE_OFFSET
        .checked_add(message.len())
        .ok_or(Ed25519ContractError::WrongLength)?;
    ensure_u16(total)?;

    let mut output = vec![2, 0];
    write_offsets(
        &mut output,
        FIRST_SIGNATURE_OFFSET,
        FIRST_PUBLIC_KEY_OFFSET,
        SHARED_MESSAGE_OFFSET,
        message.len(),
    )?;
    write_offsets(
        &mut output,
        SECOND_SIGNATURE_OFFSET,
        SECOND_PUBLIC_KEY_OFFSET,
        SHARED_MESSAGE_OFFSET,
        message.len(),
    )?;
    output.extend_from_slice(claim_key);
    output.extend_from_slice(claim_signature);
    output.extend_from_slice(destination_wallet);
    output.extend_from_slice(destination_signature);
    output.extend_from_slice(message);
    debug_assert_eq!(output.len(), total);
    Ok(output)
}

#[allow(clippy::too_many_arguments)]
pub fn verify_runtime_binding_ed25519_data(
    program_id: &[u8; 32],
    ed25519_instruction_index: usize,
    channel_instruction_index: usize,
    data: &[u8],
    expected_claim_key: &[u8; 32],
    expected_destination: &[u8; 32],
    expected_message: &[u8],
) -> Result<(), Ed25519ContractError> {
    verify_position_and_program(
        program_id,
        ed25519_instruction_index,
        channel_instruction_index,
    )?;
    ensure_header(data)?;
    let expected = build_runtime_binding_ed25519_data(
        expected_claim_key,
        &[0; 64],
        expected_destination,
        &[0; 64],
        expected_message,
    )?;
    if data.len() != expected.len() {
        return Err(Ed25519ContractError::WrongLength);
    }
    if data[2..BINDING_HEADER] != expected[2..BINDING_HEADER] {
        ensure_self_contained(&data[2..BINDING_HEADER])?;
        return Err(Ed25519ContractError::NonCanonicalOffsets);
    }
    if &data[FIRST_PUBLIC_KEY_OFFSET..FIRST_PUBLIC_KEY_OFFSET + 32] != expected_claim_key
        || &data[SECOND_PUBLIC_KEY_OFFSET..SECOND_PUBLIC_KEY_OFFSET + 32]
            != expected_destination
    {
        return Err(Ed25519ContractError::WrongPublicKey);
    }
    if &data[SHARED_MESSAGE_OFFSET..] != expected_message {
        return Err(Ed25519ContractError::WrongMessage);
    }
    Ok(())
}

pub fn extract_runtime_binding_ed25519_message<'a>(
    program_id: &[u8; 32],
    ed25519_instruction_index: usize,
    channel_instruction_index: usize,
    data: &'a [u8],
    expected_claim_key: &[u8; 32],
) -> Result<ExtractedBindingMessage<'a>, Ed25519ContractError> {
    verify_position_and_program(
        program_id,
        ed25519_instruction_index,
        channel_instruction_index,
    )?;
    ensure_header(data)?;
    if data.len() < SHARED_MESSAGE_OFFSET {
        return Err(Ed25519ContractError::WrongLength);
    }
    let message_len = data.len() - SHARED_MESSAGE_OFFSET;
    ensure_u16(message_len)?;

    let expected = build_runtime_binding_ed25519_data(
        expected_claim_key,
        &[0; 64],
        &[0; 32],
        &[0; 64],
        &vec![0; message_len],
    )?;
    if data[2..BINDING_HEADER] != expected[2..BINDING_HEADER] {
        ensure_self_contained(&data[2..BINDING_HEADER])?;
        return Err(Ed25519ContractError::NonCanonicalOffsets);
    }
    if &data[FIRST_PUBLIC_KEY_OFFSET..FIRST_PUBLIC_KEY_OFFSET + 32] != expected_claim_key {
        return Err(Ed25519ContractError::WrongPublicKey);
    }
    let destination_wallet: [u8; 32] = data
        [SECOND_PUBLIC_KEY_OFFSET..SECOND_PUBLIC_KEY_OFFSET + 32]
        .try_into()
        .map_err(|_| Ed25519ContractError::WrongLength)?;

    Ok(ExtractedBindingMessage {
        destination_wallet,
        message: &data[SHARED_MESSAGE_OFFSET..],
    })
}

fn verify_position_and_program(
    program_id: &[u8; 32],
    ed25519_instruction_index: usize,
    channel_instruction_index: usize,
) -> Result<(), Ed25519ContractError> {
    if program_id != &ED25519_PROGRAM_ID_BYTES {
        return Err(Ed25519ContractError::WrongProgramId);
    }
    if ed25519_instruction_index.checked_add(1) != Some(channel_instruction_index) {
        return Err(Ed25519ContractError::NotImmediatelyPreceding);
    }
    Ok(())
}

fn ensure_header(data: &[u8]) -> Result<(), Ed25519ContractError> {
    if data.len() < BINDING_HEADER {
        return Err(Ed25519ContractError::WrongLength);
    }
    if data[0] != 2 {
        return Err(Ed25519ContractError::WrongSignatureCount);
    }
    if data[1] != 0 {
        return Err(Ed25519ContractError::NonZeroPadding);
    }
    Ok(())
}

fn ensure_self_contained(offsets: &[u8]) -> Result<(), Ed25519ContractError> {
    for record in offsets.chunks_exact(OFFSETS_SIZE) {
        for index_offset in [2, 6, 12] {
            let value = u16::from_le_bytes([record[index_offset], record[index_offset + 1]]);
            if value != CURRENT_INSTRUCTION {
                return Err(Ed25519ContractError::ExternalInstructionReference);
            }
        }
    }
    Ok(())
}

fn write_offsets(
    output: &mut Vec<u8>,
    signature_offset: usize,
    public_key_offset: usize,
    message_offset: usize,
    message_len: usize,
) -> Result<(), Ed25519ContractError> {
    for value in [
        signature_offset,
        public_key_offset,
        message_offset,
        message_len,
    ] {
        ensure_u16(value)?;
    }
    output.extend_from_slice(&(signature_offset as u16).to_le_bytes());
    output.extend_from_slice(&CURRENT_INSTRUCTION.to_le_bytes());
    output.extend_from_slice(&(public_key_offset as u16).to_le_bytes());
    output.extend_from_slice(&CURRENT_INSTRUCTION.to_le_bytes());
    output.extend_from_slice(&(message_offset as u16).to_le_bytes());
    output.extend_from_slice(&(message_len as u16).to_le_bytes());
    output.extend_from_slice(&CURRENT_INSTRUCTION.to_le_bytes());
    Ok(())
}

fn ensure_u16(value: usize) -> Result<u16, Ed25519ContractError> {
    u16::try_from(value).map_err(|_| Ed25519ContractError::WrongLength)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ed25519::{build_binding_ed25519_data, ED25519_PROGRAM_ID_BYTES};

    #[test]
    fn runtime_binding_shares_one_exact_message_range() {
        let message = b"foundry.channels.recipient-binding/v1";
        let data = build_runtime_binding_ed25519_data(
            &[1; 32],
            &[2; 64],
            &[3; 32],
            &[4; 64],
            message,
        )
        .unwrap();
        assert_eq!(data.len(), SHARED_MESSAGE_OFFSET + message.len());
        assert_eq!(
            verify_runtime_binding_ed25519_data(
                &ED25519_PROGRAM_ID_BYTES,
                8,
                9,
                &data,
                &[1; 32],
                &[3; 32],
                message,
            ),
            Ok(())
        );
        assert_eq!(
            extract_runtime_binding_ed25519_message(
                &ED25519_PROGRAM_ID_BYTES,
                8,
                9,
                &data,
                &[1; 32],
            ),
            Ok(ExtractedBindingMessage {
                destination_wallet: [3; 32],
                message: message.as_slice(),
            })
        );
    }

    #[test]
    fn historical_duplicated_layout_remains_byte_distinct_and_reproducible() {
        let message = b"binding";
        let historical =
            build_binding_ed25519_data(&[1; 32], &[2; 64], &[3; 32], &[4; 64], message).unwrap();
        let runtime = build_runtime_binding_ed25519_data(
            &[1; 32],
            &[2; 64],
            &[3; 32],
            &[4; 64],
            message,
        )
        .unwrap();
        assert_eq!(historical.len(), 222 + 2 * message.len());
        assert_eq!(runtime.len(), 222 + message.len());
        assert_ne!(historical, runtime);
    }

    #[test]
    fn canonical_780_byte_binding_drops_from_1782_to_1002_instruction_bytes() {
        let message = vec![7_u8; 780];
        let historical =
            build_binding_ed25519_data(&[1; 32], &[2; 64], &[3; 32], &[4; 64], &message).unwrap();
        let runtime = build_runtime_binding_ed25519_data(
            &[1; 32],
            &[2; 64],
            &[3; 32],
            &[4; 64],
            &message,
        )
        .unwrap();
        assert_eq!(historical.len(), 1_782);
        assert_eq!(runtime.len(), 1_002);
    }

    #[test]
    fn runtime_layout_rejects_external_reference_or_wrong_claim_key() {
        let message = b"binding";
        let mut data = build_runtime_binding_ed25519_data(
            &[1; 32],
            &[2; 64],
            &[3; 32],
            &[4; 64],
            message,
        )
        .unwrap();
        data[4] = 0;
        data[5] = 0;
        assert_eq!(
            extract_runtime_binding_ed25519_message(
                &ED25519_PROGRAM_ID_BYTES,
                8,
                9,
                &data,
                &[1; 32],
            ),
            Err(Ed25519ContractError::ExternalInstructionReference)
        );

        let data = build_runtime_binding_ed25519_data(
            &[1; 32],
            &[2; 64],
            &[3; 32],
            &[4; 64],
            message,
        )
        .unwrap();
        assert_eq!(
            extract_runtime_binding_ed25519_message(
                &ED25519_PROGRAM_ID_BYTES,
                8,
                9,
                &data,
                &[9; 32],
            ),
            Err(Ed25519ContractError::WrongPublicKey)
        );
    }
}
