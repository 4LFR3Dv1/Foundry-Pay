//! FC-SOL-006 executable ChannelVault program runtime.
//!
//! This first runtime slice deliberately implements only state-authority
//! handlers that require no token CPI: voucher activation, recipient binding,
//! and close request. The remaining five operations fail closed until their
//! System/SPL CPI contracts are implemented and tested.

use foundry_channel_vault_account_model::{
    verify_channel_pda, ChannelState, ChannelStateError, StatusCode, CHANNEL_STATE_SPACE,
};
use foundry_channel_vault_instruction_contract::{
    extract_binding_ed25519_message, extract_voucher_ed25519_message,
    verify_recipient_binding_signed_message, verify_voucher_signed_message, ContractErrorCode,
    Ed25519ContractError, RuntimeAuthorityError, RuntimeInstructionV2,
    RuntimeInstructionV2DecodeError, VerifiedRecipientBindingAuthority, VerifiedVoucherAuthority,
};
use foundry_channel_vault_transition_model::{
    apply as apply_model, AccountOwnership, Lifecycle, ModelError, ModelInstruction, ModelState,
};
use solana_program::{
    account_info::AccountInfo,
    clock::Clock,
    entrypoint,
    entrypoint::ProgramResult,
    msg,
    program_error::ProgramError,
    pubkey::Pubkey,
    sysvar::{
        instructions::{
            load_current_index_checked, load_instruction_at_checked, ID as INSTRUCTIONS_SYSVAR_ID,
        },
        Sysvar,
    },
};

entrypoint!(process_instruction);

pub fn process_instruction(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    instruction_data: &[u8],
) -> ProgramResult {
    let instruction = RuntimeInstructionV2::decode(instruction_data).map_err(map_decode_error)?;
    match instruction {
        RuntimeInstructionV2::ActivateVoucher { voucher_hash } => {
            process_activate_voucher(program_id, accounts, voucher_hash)
        }
        RuntimeInstructionV2::BindRecipient { binding_hash } => {
            process_bind_recipient(program_id, accounts, binding_hash)
        }
        RuntimeInstructionV2::RequestClose { claim_deadline } => {
            process_request_close(program_id, accounts, claim_deadline)
        }
        RuntimeInstructionV2::InitializeChannel { .. }
        | RuntimeInstructionV2::FundChannel { .. }
        | RuntimeInstructionV2::Settle { .. }
        | RuntimeInstructionV2::RefundUnallocated { .. }
        | RuntimeInstructionV2::FinalizeClose { .. } => Err(ProgramError::InvalidInstructionData),
    }
}

fn process_activate_voucher(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    voucher_hash: [u8; 32],
) -> ProgramResult {
    if accounts.len() != 2 {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    let channel = &accounts[0];
    let instructions_sysvar = &accounts[1];
    require_instructions_sysvar(instructions_sysvar)?;

    let mut state = read_channel(program_id, channel)?;
    let current_index = load_current_index_checked(instructions_sysvar)
        .map_err(|_| custom(ContractErrorCode::Ed25519NotImmediatelyPreceding))?;
    if current_index == 0 {
        return Err(custom(ContractErrorCode::Ed25519NotImmediatelyPreceding));
    }
    let previous_index = current_index - 1;
    let previous = load_instruction_at_checked(previous_index as usize, instructions_sysvar)
        .map_err(|_| custom(ContractErrorCode::Ed25519NotImmediatelyPreceding))?;

    let message = extract_voucher_ed25519_message(
        &previous.program_id.to_bytes(),
        previous_index as usize,
        current_index as usize,
        &previous.data,
        &state.sender.to_bytes(),
    )
    .map_err(map_ed25519_error)?;

    let authority = verify_voucher_signed_message(
        message,
        voucher_hash,
        &state,
        program_id,
        channel.key,
    )
    .map_err(map_runtime_authority_error)?;

    let now = Clock::get()?.unix_timestamp;
    apply_voucher_authority(&mut state, channel.key, &authority, now)?;
    write_channel(channel, &state)?;

    msg!(
        "foundry_channel_vault:event=VoucherActivated sequence={} cumulative_authorized={}",
        authority.sequence,
        authority.cumulative_authorized
    );
    Ok(())
}

fn process_bind_recipient(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    binding_hash: [u8; 32],
) -> ProgramResult {
    if accounts.len() != 2 {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    let channel = &accounts[0];
    let instructions_sysvar = &accounts[1];
    require_instructions_sysvar(instructions_sysvar)?;

    let mut state = read_channel(program_id, channel)?;
    let current_index = load_current_index_checked(instructions_sysvar)
        .map_err(|_| custom(ContractErrorCode::Ed25519NotImmediatelyPreceding))?;
    if current_index == 0 {
        return Err(custom(ContractErrorCode::Ed25519NotImmediatelyPreceding));
    }
    let previous_index = current_index - 1;
    let previous = load_instruction_at_checked(previous_index as usize, instructions_sysvar)
        .map_err(|_| custom(ContractErrorCode::Ed25519NotImmediatelyPreceding))?;

    let extracted = extract_binding_ed25519_message(
        &previous.program_id.to_bytes(),
        previous_index as usize,
        current_index as usize,
        &previous.data,
        &state.recipient_claim_pubkey.to_bytes(),
    )
    .map_err(map_ed25519_error)?;
    let destination = Pubkey::new_from_array(extracted.destination_wallet);

    let authority = verify_recipient_binding_signed_message(
        extracted.message,
        binding_hash,
        &destination,
        &state,
        program_id,
        channel.key,
    )
    .map_err(map_runtime_authority_error)?;

    let now = Clock::get()?.unix_timestamp;
    apply_binding_authority(&mut state, channel.key, &authority, now)?;
    write_channel(channel, &state)?;

    msg!(
        "foundry_channel_vault:event=RecipientBound destination={}",
        authority.destination_wallet
    );
    Ok(())
}

fn process_request_close(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    claim_deadline: i64,
) -> ProgramResult {
    if accounts.len() != 2 {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    let channel = &accounts[0];
    let sender = &accounts[1];

    let mut state = read_channel(program_id, channel)?;
    if !sender.is_signer {
        return Err(custom(ContractErrorCode::MissingSigner));
    }
    if sender.key != &state.sender {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }

    let now = Clock::get()?.unix_timestamp;
    apply_close_request(&mut state, channel.key, claim_deadline, now)?;
    write_channel(channel, &state)?;

    msg!(
        "foundry_channel_vault:event=CloseRequested claim_deadline={}",
        claim_deadline
    );
    Ok(())
}

fn require_instructions_sysvar(account: &AccountInfo) -> ProgramResult {
    if account.key != &INSTRUCTIONS_SYSVAR_ID {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    Ok(())
}

fn read_channel(program_id: &Pubkey, channel: &AccountInfo) -> Result<ChannelState, ProgramError> {
    if !channel.is_writable {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    if channel.owner != program_id {
        return Err(custom(ContractErrorCode::WrongAccountOwner));
    }
    let data = channel.try_borrow_data()?;
    let state = ChannelState::deserialize(&data).map_err(map_state_error)?;
    if !verify_channel_pda(
        channel.key,
        state.bump,
        program_id,
        &state.sender,
        &state.mint,
        &state.channel_nonce,
    ) {
        return Err(custom(ContractErrorCode::WrongPda));
    }
    Ok(state)
}

fn write_channel(channel: &AccountInfo, state: &ChannelState) -> ProgramResult {
    let encoded = state.serialize().map_err(map_state_error)?;
    let mut data = channel.try_borrow_mut_data()?;
    if data.len() != CHANNEL_STATE_SPACE {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    data.copy_from_slice(&encoded);
    Ok(())
}

fn apply_voucher_authority(
    state: &mut ChannelState,
    channel_key: &Pubkey,
    authority: &VerifiedVoucherAuthority,
    now: i64,
) -> ProgramResult {
    let transition = apply_model(
        &model_state(state, channel_key)?,
        &ModelInstruction::Activate {
            sequence: authority.sequence,
            cumulative_authorized: authority.cumulative_authorized,
            voucher_expiry: authority.expires_at,
        },
        now,
    )
    .map_err(map_model_error)?;

    state.activated_authorized_total = transition.state.activated;
    state.latest_activated_sequence = transition.state.latest_sequence;
    state.latest_activated_voucher_hash = authority.voucher_hash;
    state.voucher_expiry_set = 1;
    state.voucher_expiry = authority.expires_at;
    Ok(())
}

fn apply_binding_authority(
    state: &mut ChannelState,
    channel_key: &Pubkey,
    authority: &VerifiedRecipientBindingAuthority,
    now: i64,
) -> ProgramResult {
    let transition = apply_model(
        &model_state(state, channel_key)?,
        &ModelInstruction::BindRecipient {
            recipient: authority.destination_wallet.to_bytes(),
        },
        now,
    )
    .map_err(map_model_error)?;

    state.recipient_wallet = Pubkey::new_from_array(transition.state.bound_recipient);
    state.recipient_bound = 1;
    Ok(())
}

fn apply_close_request(
    state: &mut ChannelState,
    channel_key: &Pubkey,
    claim_deadline: i64,
    now: i64,
) -> ProgramResult {
    let transition = apply_model(
        &model_state(state, channel_key)?,
        &ModelInstruction::RequestClose { claim_deadline },
        now,
    )
    .map_err(map_model_error)?;

    if transition.state.lifecycle != Lifecycle::Closing {
        return Err(custom(ContractErrorCode::LifecycleViolation));
    }
    state.status = StatusCode::Closing;
    state.close_requested = 1;
    state.close_requested_at = now;
    state.claim_deadline_set = 1;
    state.claim_deadline = claim_deadline;
    Ok(())
}

fn model_state(state: &ChannelState, channel_key: &Pubkey) -> Result<ModelState, ProgramError> {
    let lifecycle = match state.status {
        StatusCode::Active => Lifecycle::Active,
        StatusCode::Closing => Lifecycle::Closing,
        StatusCode::Closed => Lifecycle::Finalized,
        _ => return Err(custom(ContractErrorCode::LifecycleViolation)),
    };
    let claim_deadline = if state.claim_deadline_set == 1 {
        Some(state.claim_deadline)
    } else {
        None
    };

    let model = ModelState {
        channel_owner: AccountOwnership::ChannelVault,
        channel_space: CHANNEL_STATE_SPACE,
        vault_owner: AccountOwnership::ClassicToken,
        lifecycle,
        funded: state.funded_total,
        activated: state.activated_authorized_total,
        settled: state.settled_total,
        refunded: state.refunded_total,
        latest_sequence: state.latest_activated_sequence,
        recipient_bound: state.recipient_bound == 1,
        bound_recipient: state.recipient_wallet.to_bytes(),
        binding_nonce_consumed: state.recipient_bound == 1,
        claim_deadline,
        mint: state.mint.to_bytes(),
        vault: state.vault_token_account.to_bytes(),
        channel_pda: channel_key.to_bytes(),
    };
    if !model.invariants_hold() {
        return Err(custom(ContractErrorCode::ConservationViolation));
    }
    Ok(model)
}

fn map_decode_error(error: RuntimeInstructionV2DecodeError) -> ProgramError {
    custom(match error {
        RuntimeInstructionV2DecodeError::WrongLength => ContractErrorCode::InvalidInstructionLength,
        RuntimeInstructionV2DecodeError::UnknownDiscriminator => ContractErrorCode::UnknownInstruction,
        RuntimeInstructionV2DecodeError::UnsupportedVersion(_) => {
            ContractErrorCode::UnsupportedInstructionVersion
        }
    })
}

fn map_state_error(error: ChannelStateError) -> ProgramError {
    custom(match error {
        ChannelStateError::WrongProgramOwner => ContractErrorCode::WrongAccountOwner,
        ChannelStateError::WrongLength { .. }
        | ChannelStateError::WrongDiscriminator
        | ChannelStateError::UnknownVersion(_)
        | ChannelStateError::UnknownStatus(_)
        | ChannelStateError::UnknownEnvironment(_)
        | ChannelStateError::UnknownNetwork(_)
        | ChannelStateError::UnknownPolicyFlags(_)
        | ChannelStateError::InvalidBoolean { .. }
        | ChannelStateError::FlagValueMismatch(_)
        | ChannelStateError::RecipientBindingMismatch
        | ChannelStateError::ReservedBytesNonZero => ContractErrorCode::WrongAccountAddress,
    })
}

fn map_ed25519_error(error: Ed25519ContractError) -> ProgramError {
    custom(match error {
        Ed25519ContractError::NotImmediatelyPreceding => {
            ContractErrorCode::Ed25519NotImmediatelyPreceding
        }
        Ed25519ContractError::WrongProgramId => ContractErrorCode::WrongEd25519Program,
        Ed25519ContractError::WrongSignatureCount
        | Ed25519ContractError::NonZeroPadding
        | Ed25519ContractError::WrongLength => ContractErrorCode::NonCanonicalEd25519Header,
        Ed25519ContractError::ExternalInstructionReference => {
            ContractErrorCode::ExternalEd25519Reference
        }
        Ed25519ContractError::NonCanonicalOffsets => ContractErrorCode::NonCanonicalEd25519Offsets,
        Ed25519ContractError::WrongPublicKey => ContractErrorCode::WrongEd25519PublicKey,
        Ed25519ContractError::WrongMessage => ContractErrorCode::WrongEd25519Message,
    })
}

fn map_runtime_authority_error(error: RuntimeAuthorityError) -> ProgramError {
    let code = match error {
        RuntimeAuthorityError::UnsupportedEnvironment => ContractErrorCode::UnsupportedProfile,
        RuntimeAuthorityError::ContextMismatch("mint") => ContractErrorCode::WrongMint,
        RuntimeAuthorityError::ContextMismatch("previous_activated_voucher_hash") => {
            ContractErrorCode::SequenceRegression
        }
        RuntimeAuthorityError::ContextMismatch("binding_nonce") => {
            ContractErrorCode::BindingNonceConsumed
        }
        RuntimeAuthorityError::ContextMismatch("destination_wallet") => {
            ContractErrorCode::RecipientSubstitution
        }
        RuntimeAuthorityError::InvalidField("cumulative_authorized_base_units") => {
            ContractErrorCode::ConservationViolation
        }
        RuntimeAuthorityError::ContextMismatch("network")
        | RuntimeAuthorityError::ContextMismatch("environment") => ContractErrorCode::UnsupportedProfile,
        RuntimeAuthorityError::InvalidJson
        | RuntimeAuthorityError::NonCanonicalJson
        | RuntimeAuthorityError::WrongObjectShape
        | RuntimeAuthorityError::MissingField(_)
        | RuntimeAuthorityError::UnknownField
        | RuntimeAuthorityError::InvalidField(_)
        | RuntimeAuthorityError::ContextMismatch(_)
        | RuntimeAuthorityError::HashMismatch
        | RuntimeAuthorityError::BindingNonceEncoding => ContractErrorCode::WrongEd25519Message,
    };
    custom(code)
}

fn map_model_error(error: ModelError) -> ProgramError {
    let code = match error {
        ModelError::Finalized => ContractErrorCode::FinalizedChannel,
        ModelError::LifecycleViolation
        | ModelError::Uninitialized
        | ModelError::AlreadyInitialized
        | ModelError::InvalidInitializationOwner
        | ModelError::AtomicInitializationFailure
        | ModelError::InvalidClaimWindow
        | ModelError::ClaimWindowOverflow
        | ModelError::ClaimWindowOpen => ContractErrorCode::LifecycleViolation,
        ModelError::ExpiredVoucher => ContractErrorCode::ExpiredAuthority,
        ModelError::SequenceReplay => ContractErrorCode::SequenceReplay,
        ModelError::BindingNonceConsumed => ContractErrorCode::BindingNonceConsumed,
        ModelError::RecipientSubstitution | ModelError::InvalidRecipient => {
            ContractErrorCode::RecipientSubstitution
        }
        ModelError::CheckedArithmeticFailure => ContractErrorCode::CheckedArithmeticFailure,
        ModelError::UnallocatedCapacity => ContractErrorCode::InsufficientUnallocatedCapacity,
        ModelError::OutstandingRight | ModelError::RecipientNotBound => {
            ContractErrorCode::InsufficientActivatedRight
        }
        ModelError::ZeroAmount | ModelError::ConservationViolation => {
            ContractErrorCode::ConservationViolation
        }
    };
    custom(code)
}

fn custom(code: ContractErrorCode) -> ProgramError {
    ProgramError::Custom(code as u32)
}

#[cfg(test)]
mod tests {
    use super::*;
    use foundry_channel_vault_account_model::{
        EnvironmentCode, NetworkCode, CHANNEL_STATE_RESERVED_BYTES, CHANNEL_STATE_VERSION_V1,
    };
    use foundry_channel_vault_instruction_contract::{
        encode_binding_nonce_u64, INITIAL_BINDING_NONCE,
    };

    fn state() -> (ChannelState, Pubkey) {
        let program_id = Pubkey::new_unique();
        let sender = Pubkey::new_unique();
        let mint = Pubkey::new_unique();
        let nonce = [7; 32];
        let (channel, bump) = foundry_channel_vault_account_model::derive_channel_pda(
            &program_id,
            &sender,
            &mint,
            &nonce,
        );
        (
            ChannelState {
                account_version: CHANNEL_STATE_VERSION_V1,
                bump,
                status: StatusCode::Active,
                environment: EnvironmentCode::DevnetFixture,
                network: NetworkCode::Solana,
                program_version: 1,
                policy_flags: 0,
                genesis_hash: [1; 32],
                channel_nonce: nonce,
                channel_id_hash: [2; 32],
                epoch: 0,
                sender,
                recipient_claim_pubkey: Pubkey::new_unique(),
                recipient_wallet: Pubkey::default(),
                recipient_bound: 0,
                binding_nonce: encode_binding_nonce_u64(INITIAL_BINDING_NONCE),
                mint,
                vault_token_account: Pubkey::new_unique(),
                decimals: 6,
                funded_total: 100,
                activated_authorized_total: 20,
                settled_total: 0,
                refunded_total: 0,
                latest_activated_sequence: 1,
                latest_activated_voucher_hash: [3; 32],
                channel_expiry_set: 0,
                channel_expiry: 0,
                voucher_expiry_set: 1,
                voucher_expiry: 1_900_000_000,
                close_requested: 0,
                close_requested_at: 0,
                claim_deadline_set: 0,
                claim_deadline: 0,
                reserved: [0; CHANNEL_STATE_RESERVED_BYTES],
            },
            channel,
        )
    }

    #[test]
    fn activation_mutates_only_authorized_runtime_fields() {
        let (mut state, channel) = state();
        let authority = VerifiedVoucherAuthority {
            sequence: 2,
            cumulative_authorized: 40,
            voucher_hash: [9; 32],
            expires_at: 1_800_001_000,
        };
        apply_voucher_authority(&mut state, &channel, &authority, 1_800_000_000).unwrap();
        assert_eq!(state.activated_authorized_total, 40);
        assert_eq!(state.latest_activated_sequence, 2);
        assert_eq!(state.latest_activated_voucher_hash, [9; 32]);
        assert_eq!(state.voucher_expiry_set, 1);
        assert_eq!(state.voucher_expiry, 1_800_001_000);
        assert_eq!(state.funded_total, 100);
        assert_eq!(state.settled_total, 0);
    }

    #[test]
    fn activation_over_funding_fails_without_mutation() {
        let (mut state, channel) = state();
        let before = state.clone();
        let authority = VerifiedVoucherAuthority {
            sequence: 2,
            cumulative_authorized: 101,
            voucher_hash: [9; 32],
            expires_at: 1_800_001_000,
        };
        assert_eq!(
            apply_voucher_authority(&mut state, &channel, &authority, 1_800_000_000),
            Err(custom(ContractErrorCode::ConservationViolation))
        );
        assert_eq!(state, before);
    }

    #[test]
    fn binding_is_one_use_and_persists_only_verified_destination() {
        let (mut state, channel) = state();
        let destination = Pubkey::new_unique();
        let authority = VerifiedRecipientBindingAuthority {
            destination_wallet: destination,
            binding_nonce: INITIAL_BINDING_NONCE,
            binding_hash: [8; 32],
            expires_at: 1_800_001_000,
        };
        apply_binding_authority(&mut state, &channel, &authority, 1_800_000_000).unwrap();
        assert_eq!(state.recipient_bound, 1);
        assert_eq!(state.recipient_wallet, destination);

        assert_eq!(
            apply_binding_authority(&mut state, &channel, &authority, 1_800_000_000),
            Err(custom(ContractErrorCode::BindingNonceConsumed))
        );
    }

    #[test]
    fn close_request_transitions_to_closing_with_exclusive_deadline() {
        let (mut state, channel) = state();
        let now = 1_800_000_000;
        let deadline = now + 900;
        apply_close_request(&mut state, &channel, deadline, now).unwrap();
        assert_eq!(state.status, StatusCode::Closing);
        assert_eq!(state.close_requested, 1);
        assert_eq!(state.close_requested_at, now);
        assert_eq!(state.claim_deadline_set, 1);
        assert_eq!(state.claim_deadline, deadline);
    }
}
