//! Canonical self-contained Ed25519 precompile layouts.

pub const ED25519_PROGRAM_ID_BYTES: [u8; 32] = [
    3, 125, 70, 214, 124, 147, 251, 190, 18, 249, 66, 143, 131, 141, 64, 255, 5, 112, 116, 73, 39,
    244, 138, 100, 252, 202, 112, 68, 128, 0, 0, 0,
];

const OFFSETS_SIZE: usize = 14;
const CURRENT_INSTRUCTION: u16 = u16::MAX;
const VOUCHER_HEADER: usize = 16;
const BINDING_HEADER: usize = 30;

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Ed25519ContractError {
    NotImmediatelyPreceding,
    WrongProgramId,
    WrongSignatureCount,
    NonZeroPadding,
    WrongLength,
    ExternalInstructionReference,
    NonCanonicalOffsets,
    WrongPublicKey,
    WrongMessage,
}

pub fn build_voucher_ed25519_data(
    sender: &[u8; 32],
    signature: &[u8; 64],
    message: &[u8],
) -> Result<Vec<u8>, Ed25519ContractError> {
    ensure_u16(message.len())?;
    let mut output = vec![1, 0];
    write_offsets(&mut output, 48, 16, 112, message.len())?;
    output.extend_from_slice(sender);
    output.extend_from_slice(signature);
    output.extend_from_slice(message);
    Ok(output)
}

pub fn verify_voucher_ed25519_data(
    program_id: &[u8; 32],
    ed25519_instruction_index: usize,
    channel_instruction_index: usize,
    data: &[u8],
    expected_sender: &[u8; 32],
    expected_message: &[u8],
) -> Result<(), Ed25519ContractError> {
    verify_position_and_program(
        program_id,
        ed25519_instruction_index,
        channel_instruction_index,
    )?;
    ensure_header(data, 1)?;
    let expected = build_voucher_ed25519_data(expected_sender, &[0; 64], expected_message)?;
    let expected_offsets = &expected[2..VOUCHER_HEADER];
    if &data[2..VOUCHER_HEADER] != expected_offsets {
        ensure_self_contained(&data[2..VOUCHER_HEADER])?;
        return Err(Ed25519ContractError::NonCanonicalOffsets);
    }
    let expected_length = 112_usize
        .checked_add(expected_message.len())
        .ok_or(Ed25519ContractError::WrongLength)?;
    if data.len() != expected_length {
        return Err(Ed25519ContractError::WrongLength);
    }
    if &data[16..48] != expected_sender {
        return Err(Ed25519ContractError::WrongPublicKey);
    }
    if &data[112..] != expected_message {
        return Err(Ed25519ContractError::WrongMessage);
    }
    Ok(())
}

pub fn build_binding_ed25519_data(
    claim_key: &[u8; 32],
    claim_signature: &[u8; 64],
    destination_wallet: &[u8; 32],
    destination_signature: &[u8; 64],
    message: &[u8],
) -> Result<Vec<u8>, Ed25519ContractError> {
    let message_len = ensure_u16(message.len())?;
    let second_key_offset = BINDING_HEADER
        .checked_add(96)
        .and_then(|value| value.checked_add(message.len()))
        .ok_or(Ed25519ContractError::WrongLength)?;
    let second_signature_offset = second_key_offset
        .checked_add(32)
        .ok_or(Ed25519ContractError::WrongLength)?;
    let second_message_offset = second_signature_offset
        .checked_add(64)
        .ok_or(Ed25519ContractError::WrongLength)?;
    ensure_u16(second_message_offset)?;
    let mut output = vec![2, 0];
    write_offsets(&mut output, 62, 30, 126, message.len())?;
    write_offsets(
        &mut output,
        second_signature_offset,
        second_key_offset,
        second_message_offset,
        message_len as usize,
    )?;
    output.extend_from_slice(claim_key);
    output.extend_from_slice(claim_signature);
    output.extend_from_slice(message);
    output.extend_from_slice(destination_wallet);
    output.extend_from_slice(destination_signature);
    output.extend_from_slice(message);
    Ok(output)
}

#[allow(clippy::too_many_arguments)]
pub fn verify_binding_ed25519_data(
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
    ensure_header(data, 2)?;
    let expected = build_binding_ed25519_data(
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
    let message_len = expected_message.len();
    let second_key_offset = BINDING_HEADER + 96 + message_len;
    let second_message_offset = BINDING_HEADER + 192 + message_len;
    if &data[BINDING_HEADER..BINDING_HEADER + 32] != expected_claim_key
        || &data[second_key_offset..second_key_offset + 32] != expected_destination
    {
        return Err(Ed25519ContractError::WrongPublicKey);
    }
    if &data[126..126 + message_len] != expected_message
        || &data[second_message_offset..second_message_offset + message_len] != expected_message
    {
        return Err(Ed25519ContractError::WrongMessage);
    }
    Ok(())
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

fn ensure_header(data: &[u8], count: u8) -> Result<(), Ed25519ContractError> {
    let header = 2 + OFFSETS_SIZE * usize::from(count);
    if data.len() < header {
        return Err(Ed25519ContractError::WrongLength);
    }
    if data[0] != count {
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
    use solana_pubkey::Pubkey;
    use std::str::FromStr;

    #[test]
    fn fixed_program_id_matches_solana_ed25519_precompile() {
        let expected = Pubkey::from_str("Ed25519SigVerify111111111111111111111111111").unwrap();
        assert_eq!(
            Pubkey::new_from_array(ED25519_PROGRAM_ID_BYTES),
            expected,
            "expected bytes: {:?}",
            expected.to_bytes()
        );
    }

    #[test]
    fn voucher_layout_is_exact_and_self_contained() {
        let message = b"foundry.channels.voucher/v1";
        let data = build_voucher_ed25519_data(&[1; 32], &[2; 64], message).unwrap();
        assert_eq!(data.len(), 112 + message.len());
        assert_eq!(
            verify_voucher_ed25519_data(&ED25519_PROGRAM_ID_BYTES, 3, 4, &data, &[1; 32], message),
            Ok(())
        );
    }

    #[test]
    fn binding_layout_duplicates_exact_message_without_overlap() {
        let message = b"foundry.channels.recipient-binding/v1";
        let data =
            build_binding_ed25519_data(&[1; 32], &[2; 64], &[3; 32], &[4; 64], message).unwrap();
        assert_eq!(data.len(), 222 + 2 * message.len());
        assert_eq!(
            verify_binding_ed25519_data(
                &ED25519_PROGRAM_ID_BYTES,
                8,
                9,
                &data,
                &[1; 32],
                &[3; 32],
                message
            ),
            Ok(())
        );
    }

    #[test]
    fn rejects_position_program_offset_key_message_and_trailing_mutations() {
        let message = b"voucher";
        let original = build_voucher_ed25519_data(&[1; 32], &[2; 64], message).unwrap();
        let verify = |data: &[u8]| {
            verify_voucher_ed25519_data(&ED25519_PROGRAM_ID_BYTES, 1, 2, data, &[1; 32], message)
        };
        assert_eq!(
            verify_voucher_ed25519_data(&[0; 32], 1, 2, &original, &[1; 32], message),
            Err(Ed25519ContractError::WrongProgramId)
        );
        assert_eq!(
            verify_voucher_ed25519_data(
                &ED25519_PROGRAM_ID_BYTES,
                2,
                2,
                &original,
                &[1; 32],
                message
            ),
            Err(Ed25519ContractError::NotImmediatelyPreceding)
        );
        for (offset, expected) in [
            (2, Ed25519ContractError::NonCanonicalOffsets),
            (16, Ed25519ContractError::WrongPublicKey),
            (112, Ed25519ContractError::WrongMessage),
        ] {
            let mut candidate = original.clone();
            candidate[offset] ^= 1;
            assert_eq!(verify(&candidate), Err(expected));
        }
        let mut trailing = original;
        trailing.push(0);
        assert_eq!(verify(&trailing), Err(Ed25519ContractError::WrongLength));
    }

    #[test]
    fn rejects_external_instruction_reference_before_generic_offset_error() {
        let mut data = build_voucher_ed25519_data(&[1; 32], &[2; 64], b"x").unwrap();
        data[4..6].copy_from_slice(&0_u16.to_le_bytes());
        assert_eq!(
            verify_voucher_ed25519_data(&ED25519_PROGRAM_ID_BYTES, 0, 1, &data, &[1; 32], b"x"),
            Err(Ed25519ContractError::ExternalInstructionReference)
        );
    }
}
