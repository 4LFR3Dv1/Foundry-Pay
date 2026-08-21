//! FC-SOL-006 executable ChannelVault program runtime.
//!
//! The runtime preserves the frozen 490-byte ChannelState, eight-operation
//! registry, classic SPL Token boundary, FC-SOL-003B signed-message authority,
//! and FC-SOL-004 transition invariants. No Program ID or deployment authority
//! is embedded here.

use foundry_channel_vault_account_model::{
    associated_token_program_id, classic_token_program_id, derive_channel_pda,
    derive_vault_address, validate_vault_account, verify_channel_pda, ChannelState,
    ChannelStateError, EnvironmentCode, NetworkCode, StatusCode, VaultAccountError,
    VaultAccountView, CHANNEL_SEED, CHANNEL_STATE_RESERVED_BYTES, CHANNEL_STATE_SPACE,
    CHANNEL_STATE_VERSION_V1,
};
use foundry_channel_vault_instruction_contract::{
    extract_binding_ed25519_message, extract_voucher_ed25519_message,
    verify_initialize_v2, verify_recipient_binding_signed_message, verify_voucher_signed_message,
    ContractErrorCode, Ed25519ContractError, RuntimeAuthorityError, RuntimeInstructionV2,
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
    instruction::{AccountMeta, Instruction},
    msg,
    program::{invoke, invoke_signed},
    program_error::ProgramError,
    pubkey::Pubkey,
    rent::Rent,
    system_instruction, system_program,
    sysvar::{
        instructions::{
            load_current_index_checked, load_instruction_at_checked, ID as INSTRUCTIONS_SYSVAR_ID,
        },
        Sysvar,
    },
};

entrypoint!(process_instruction);

const CLASSIC_TOKEN_ACCOUNT_LEN: usize = 165;
const CLASSIC_MINT_LEN: usize = 82;
const TOKEN_ACCOUNT_INITIALIZED: u8 = 1;
const TOKEN_MINT_INITIALIZED: u8 = 1;
const TOKEN_INSTRUCTION_CLOSE_ACCOUNT: u8 = 9;
const TOKEN_INSTRUCTION_TRANSFER_CHECKED: u8 = 12;
const ATA_INSTRUCTION_CREATE_IDEMPOTENT: u8 = 1;

pub fn process_instruction(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    instruction_data: &[u8],
) -> ProgramResult {
    let instruction = RuntimeInstructionV2::decode(instruction_data).map_err(map_decode_error)?;
    match instruction {
        RuntimeInstructionV2::InitializeChannel {
            channel_nonce,
            recipient_claim_pubkey,
            decimals,
            channel_expiry,
            genesis_hash,
            channel_id_hash,
            environment,
            policy_flags,
            binding_nonce,
        } => process_initialize_channel(
            program_id,
            accounts,
            channel_nonce,
            recipient_claim_pubkey,
            decimals,
            channel_expiry,
            genesis_hash,
            channel_id_hash,
            environment,
            policy_flags,
            binding_nonce,
        ),
        RuntimeInstructionV2::FundChannel { amount } => {
            process_fund_channel(program_id, accounts, amount)
        }
        RuntimeInstructionV2::ActivateVoucher { voucher_hash } => {
            process_activate_voucher(program_id, accounts, voucher_hash)
        }
        RuntimeInstructionV2::BindRecipient { binding_hash } => {
            process_bind_recipient(program_id, accounts, binding_hash)
        }
        RuntimeInstructionV2::Settle {
            amount,
            obligation_hash,
        } => process_settle(program_id, accounts, amount, obligation_hash),
        RuntimeInstructionV2::RequestClose { claim_deadline } => {
            process_request_close(program_id, accounts, claim_deadline)
        }
        RuntimeInstructionV2::RefundUnallocated {
            amount,
            refund_request_hash,
        } => process_refund_unallocated(program_id, accounts, amount, refund_request_hash),
        RuntimeInstructionV2::FinalizeClose { finalization_hash } => {
            process_finalize_close(program_id, accounts, finalization_hash)
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn process_initialize_channel(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    channel_nonce: [u8; 32],
    recipient_claim_pubkey: Pubkey,
    decimals: u8,
    channel_expiry: i64,
    genesis_hash: [u8; 32],
    channel_id_hash: [u8; 32],
    environment: u8,
    policy_flags: u32,
    binding_nonce: u64,
) -> ProgramResult {
    if accounts.len() != 7 {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    let channel = &accounts[0];
    let sender = &accounts[1];
    let mint = &accounts[2];
    let vault = &accounts[3];
    let system_program_account = &accounts[4];
    let token_program = &accounts[5];
    let associated_token_program = &accounts[6];

    require_signer(sender)?;
    if !sender.is_writable || !channel.is_writable || !vault.is_writable {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    require_program_account(system_program_account, &system_program::ID)?;
    require_program_account(token_program, &classic_token_program_id())?;
    require_program_account(associated_token_program, &associated_token_program_id())?;

    let mint_view = read_classic_mint(mint, token_program.key)?;
    if mint_view.decimals != decimals {
        return Err(custom(ContractErrorCode::WrongMint));
    }

    let runtime_instruction = RuntimeInstructionV2::InitializeChannel {
        channel_nonce,
        recipient_claim_pubkey,
        decimals,
        channel_expiry,
        genesis_hash,
        channel_id_hash,
        environment,
        policy_flags,
        binding_nonce,
    };
    let verified = verify_initialize_v2(&runtime_instruction).map_err(map_runtime_authority_error)?;

    let (expected_channel, bump) = derive_channel_pda(program_id, sender.key, mint.key, &channel_nonce);
    if expected_channel != *channel.key {
        return Err(custom(ContractErrorCode::WrongPda));
    }
    let expected_vault = derive_vault_address(channel.key, mint.key);
    if expected_vault != *vault.key {
        return Err(custom(ContractErrorCode::WrongVault));
    }
    if channel.lamports() != 0 || !channel.data_is_empty() || channel.owner != &system_program::ID {
        return Err(custom(ContractErrorCode::WrongAccountOwner));
    }

    let now = Clock::get()?.unix_timestamp;
    if channel_expiry < 0 || (channel_expiry > 0 && channel_expiry <= now) {
        return Err(custom(ContractErrorCode::ExpiredAuthority));
    }

    let projected = apply_model(
        &ModelState::absent(),
        &ModelInstruction::Initialize {
            mint: mint.key.to_bytes(),
            vault: vault.key.to_bytes(),
            channel_pda: channel.key.to_bytes(),
            injected_fault: None,
        },
        now,
    )
    .map_err(map_model_error)?;
    if projected.state.lifecycle != Lifecycle::Active {
        return Err(custom(ContractErrorCode::LifecycleViolation));
    }

    let rent = Rent::get()?;
    let lamports = rent.minimum_balance(CHANNEL_STATE_SPACE);
    let create_channel = system_instruction::create_account(
        sender.key,
        channel.key,
        lamports,
        CHANNEL_STATE_SPACE as u64,
        program_id,
    );
    let bump_seed = [bump];
    let channel_seeds: &[&[u8]] = &[
        CHANNEL_SEED,
        sender.key.as_ref(),
        mint.key.as_ref(),
        &channel_nonce,
        &bump_seed,
    ];
    invoke_signed(
        &create_channel,
        &[
            sender.clone(),
            channel.clone(),
            system_program_account.clone(),
        ],
        &[channel_seeds],
    )?;

    let create_vault = associated_token_create_idempotent_instruction(
        sender.key,
        vault.key,
        channel.key,
        mint.key,
    );
    invoke(
        &create_vault,
        &[
            sender.clone(),
            vault.clone(),
            channel.clone(),
            mint.clone(),
            system_program_account.clone(),
            token_program.clone(),
            associated_token_program.clone(),
        ],
    )?;

    let vault_view = read_classic_token_account(vault, token_program.key)?;
    if vault_view.amount != 0 {
        return Err(custom(ContractErrorCode::ConservationViolation));
    }
    if vault_view.mint != *mint.key || vault_view.authority != *channel.key {
        return Err(custom(ContractErrorCode::WrongVaultAuthority));
    }

    let state = ChannelState {
        account_version: CHANNEL_STATE_VERSION_V1,
        bump,
        status: StatusCode::Active,
        environment: EnvironmentCode::try_from(verified.environment)
            .map_err(|_| custom(ContractErrorCode::UnsupportedProfile))?,
        network: NetworkCode::Solana,
        program_version: 1,
        policy_flags: verified.policy_flags,
        genesis_hash: verified.genesis_hash,
        channel_nonce,
        channel_id_hash: verified.channel_id_hash,
        epoch: 0,
        sender: *sender.key,
        recipient_claim_pubkey,
        recipient_wallet: Pubkey::default(),
        recipient_bound: 0,
        binding_nonce: verified.binding_nonce_slot,
        mint: *mint.key,
        vault_token_account: *vault.key,
        decimals,
        funded_total: 0,
        activated_authorized_total: 0,
        settled_total: 0,
        refunded_total: 0,
        latest_activated_sequence: 0,
        latest_activated_voucher_hash: verified.latest_activated_voucher_hash,
        channel_expiry_set: u8::from(channel_expiry > 0),
        channel_expiry: if channel_expiry > 0 { channel_expiry } else { 0 },
        voucher_expiry_set: 0,
        voucher_expiry: 0,
        close_requested: 0,
        close_requested_at: 0,
        claim_deadline_set: 0,
        claim_deadline: 0,
        reserved: [0; CHANNEL_STATE_RESERVED_BYTES],
    };
    write_channel(channel, &state)?;

    msg!("foundry_channel_vault:event=ChannelInitialized channel={}", channel.key);
    Ok(())
}

fn process_fund_channel(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    amount: u64,
) -> ProgramResult {
    if accounts.len() != 6 {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    let channel = &accounts[0];
    let sender = &accounts[1];
    let sender_token = &accounts[2];
    let vault = &accounts[3];
    let mint = &accounts[4];
    let token_program = &accounts[5];

    let mut state = read_channel(program_id, channel)?;
    require_signer(sender)?;
    if sender.key != &state.sender {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    require_program_account(token_program, &classic_token_program_id())?;
    require_state_mint(&state, mint, token_program.key)?;

    if *sender_token.key != derive_vault_address(&state.sender, &state.mint) {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    let source_before = read_classic_token_account(sender_token, token_program.key)?;
    if source_before.mint != state.mint || source_before.authority != state.sender {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    let vault_before = validate_runtime_vault(&state, channel.key, program_id, vault, token_program)?;
    require_vault_matches_state(&state, vault_before.amount)?;

    let now = Clock::get()?.unix_timestamp;
    let transition = apply_model(
        &model_state(&state, channel.key)?,
        &ModelInstruction::Fund { amount },
        now,
    )
    .map_err(map_model_error)?;
    if source_before.amount < amount {
        return Err(ProgramError::InsufficientFunds);
    }

    let transfer = token_transfer_checked_instruction(
        sender_token.key,
        mint.key,
        vault.key,
        sender.key,
        amount,
        state.decimals,
    );
    invoke(
        &transfer,
        &[
            sender_token.clone(),
            mint.clone(),
            vault.clone(),
            sender.clone(),
            token_program.clone(),
        ],
    )?;

    let source_after = read_classic_token_account(sender_token, token_program.key)?;
    let vault_after = read_classic_token_account(vault, token_program.key)?;
    require_exact_transfer(
        source_before.amount,
        source_after.amount,
        vault_before.amount,
        vault_after.amount,
        amount,
    )?;

    state.funded_total = transition.state.funded;
    require_vault_matches_state(&state, vault_after.amount)?;
    write_channel(channel, &state)?;
    msg!("foundry_channel_vault:event=ChannelFunded amount={}", amount);
    Ok(())
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

fn process_settle(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    amount: u64,
    obligation_hash: [u8; 32],
) -> ProgramResult {
    if accounts.len() != 5 {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    let channel = &accounts[0];
    let vault = &accounts[1];
    let recipient_token = &accounts[2];
    let mint = &accounts[3];
    let token_program = &accounts[4];

    let mut state = read_channel(program_id, channel)?;
    require_program_account(token_program, &classic_token_program_id())?;
    require_state_mint(&state, mint, token_program.key)?;
    if state.recipient_bound != 1 {
        return Err(custom(ContractErrorCode::InsufficientActivatedRight));
    }
    let expected_recipient = derive_vault_address(&state.recipient_wallet, &state.mint);
    if recipient_token.key != &expected_recipient {
        return Err(custom(ContractErrorCode::RecipientSubstitution));
    }
    let destination_before = read_classic_token_account(recipient_token, token_program.key)?;
    if destination_before.mint != state.mint || destination_before.authority != state.recipient_wallet {
        return Err(custom(ContractErrorCode::RecipientSubstitution));
    }
    let vault_before = validate_runtime_vault(&state, channel.key, program_id, vault, token_program)?;
    require_vault_matches_state(&state, vault_before.amount)?;

    let now = Clock::get()?.unix_timestamp;
    let transition = apply_model(
        &model_state(&state, channel.key)?,
        &ModelInstruction::Settle {
            caller: [0; 32],
            amount,
            obligation_hash,
            supplied_destination: recipient_token.key.to_bytes(),
        },
        now,
    )
    .map_err(map_model_error)?;

    let transfer = token_transfer_checked_instruction(
        vault.key,
        mint.key,
        recipient_token.key,
        channel.key,
        amount,
        state.decimals,
    );
    let bump_seed = [state.bump];
    let channel_seeds: &[&[u8]] = &[
        CHANNEL_SEED,
        state.sender.as_ref(),
        state.mint.as_ref(),
        &state.channel_nonce,
        &bump_seed,
    ];
    invoke_signed(
        &transfer,
        &[
            vault.clone(),
            mint.clone(),
            recipient_token.clone(),
            channel.clone(),
            token_program.clone(),
        ],
        &[channel_seeds],
    )?;

    let vault_after = read_classic_token_account(vault, token_program.key)?;
    let destination_after = read_classic_token_account(recipient_token, token_program.key)?;
    require_exact_transfer(
        vault_before.amount,
        vault_after.amount,
        destination_before.amount,
        destination_after.amount,
        amount,
    )?;

    state.settled_total = transition.state.settled;
    require_vault_matches_state(&state, vault_after.amount)?;
    write_channel(channel, &state)?;
    msg!(
        "foundry_channel_vault:event=SettlementExecuted amount={} obligation_hash={:?}",
        amount,
        obligation_hash
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
    require_signer(sender)?;
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

fn process_refund_unallocated(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    amount: u64,
    refund_request_hash: [u8; 32],
) -> ProgramResult {
    if accounts.len() != 6 {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    let channel = &accounts[0];
    let sender = &accounts[1];
    let vault = &accounts[2];
    let sender_token = &accounts[3];
    let mint = &accounts[4];
    let token_program = &accounts[5];

    let mut state = read_channel(program_id, channel)?;
    require_signer(sender)?;
    if sender.key != &state.sender {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    require_program_account(token_program, &classic_token_program_id())?;
    require_state_mint(&state, mint, token_program.key)?;
    if sender_token.key != &derive_vault_address(&state.sender, &state.mint) {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    let destination_before = read_classic_token_account(sender_token, token_program.key)?;
    if destination_before.mint != state.mint || destination_before.authority != state.sender {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    let vault_before = validate_runtime_vault(&state, channel.key, program_id, vault, token_program)?;
    require_vault_matches_state(&state, vault_before.amount)?;

    let now = Clock::get()?.unix_timestamp;
    let transition = apply_model(
        &model_state(&state, channel.key)?,
        &ModelInstruction::RefundUnallocated { amount },
        now,
    )
    .map_err(map_model_error)?;

    let transfer = token_transfer_checked_instruction(
        vault.key,
        mint.key,
        sender_token.key,
        channel.key,
        amount,
        state.decimals,
    );
    let bump_seed = [state.bump];
    let channel_seeds: &[&[u8]] = &[
        CHANNEL_SEED,
        state.sender.as_ref(),
        state.mint.as_ref(),
        &state.channel_nonce,
        &bump_seed,
    ];
    invoke_signed(
        &transfer,
        &[
            vault.clone(),
            mint.clone(),
            sender_token.clone(),
            channel.clone(),
            token_program.clone(),
        ],
        &[channel_seeds],
    )?;

    let vault_after = read_classic_token_account(vault, token_program.key)?;
    let destination_after = read_classic_token_account(sender_token, token_program.key)?;
    require_exact_transfer(
        vault_before.amount,
        vault_after.amount,
        destination_before.amount,
        destination_after.amount,
        amount,
    )?;

    state.refunded_total = transition.state.refunded;
    require_vault_matches_state(&state, vault_after.amount)?;
    write_channel(channel, &state)?;
    msg!(
        "foundry_channel_vault:event=RefundExecuted amount={} request_hash={:?}",
        amount,
        refund_request_hash
    );
    Ok(())
}

fn process_finalize_close(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    finalization_hash: [u8; 32],
) -> ProgramResult {
    if accounts.len() != 3 {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    let channel = &accounts[0];
    let sender = &accounts[1];
    let vault = &accounts[2];

    let mut state = read_channel(program_id, channel)?;
    require_signer(sender)?;
    if sender.key != &state.sender {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }

    let vault_view = validate_runtime_vault_without_program_meta(&state, channel.key, program_id, vault)?;
    require_vault_matches_state(&state, vault_view.amount)?;
    if vault_view.amount != 0 {
        return Err(custom(ContractErrorCode::ConservationViolation));
    }

    let now = Clock::get()?.unix_timestamp;
    let transition = apply_model(
        &model_state(&state, channel.key)?,
        &ModelInstruction::FinalizeClose,
        now,
    )
    .map_err(map_model_error)?;
    if transition.state.lifecycle != Lifecycle::Finalized {
        return Err(custom(ContractErrorCode::LifecycleViolation));
    }

    state.status = StatusCode::Closed;
    write_channel(channel, &state)?;
    msg!(
        "foundry_channel_vault:event=ChannelFinalized finalization_hash={:?}",
        finalization_hash
    );
    Ok(())
}

fn require_signer(account: &AccountInfo) -> ProgramResult {
    if !account.is_signer {
        Err(custom(ContractErrorCode::MissingSigner))
    } else {
        Ok(())
    }
}

fn require_program_account(account: &AccountInfo, expected: &Pubkey) -> ProgramResult {
    if account.key != expected || !account.executable {
        return Err(custom(ContractErrorCode::UnsupportedTokenProgram));
    }
    Ok(())
}

fn require_instructions_sysvar(account: &AccountInfo) -> ProgramResult {
    if account.key != &INSTRUCTIONS_SYSVAR_ID {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    Ok(())
}

fn require_state_mint(
    state: &ChannelState,
    mint: &AccountInfo,
    token_program: &Pubkey,
) -> ProgramResult {
    if mint.key != &state.mint {
        return Err(custom(ContractErrorCode::WrongMint));
    }
    let mint_view = read_classic_mint(mint, token_program)?;
    if mint_view.decimals != state.decimals {
        return Err(custom(ContractErrorCode::WrongMint));
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

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct TokenAccountRuntimeView {
    mint: Pubkey,
    authority: Pubkey,
    amount: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct MintRuntimeView {
    decimals: u8,
}

fn read_classic_mint(
    account: &AccountInfo,
    token_program: &Pubkey,
) -> Result<MintRuntimeView, ProgramError> {
    if token_program != &classic_token_program_id() || account.owner != token_program {
        return Err(custom(ContractErrorCode::UnsupportedTokenProgram));
    }
    let data = account.try_borrow_data()?;
    if data.len() != CLASSIC_MINT_LEN || data[45] != TOKEN_MINT_INITIALIZED {
        return Err(custom(ContractErrorCode::WrongMint));
    }
    Ok(MintRuntimeView { decimals: data[44] })
}

fn read_classic_token_account(
    account: &AccountInfo,
    token_program: &Pubkey,
) -> Result<TokenAccountRuntimeView, ProgramError> {
    if token_program != &classic_token_program_id() || account.owner != token_program {
        return Err(custom(ContractErrorCode::UnsupportedTokenProgram));
    }
    let data = account.try_borrow_data()?;
    if data.len() != CLASSIC_TOKEN_ACCOUNT_LEN || data[108] != TOKEN_ACCOUNT_INITIALIZED {
        return Err(custom(ContractErrorCode::WrongAccountAddress));
    }
    Ok(TokenAccountRuntimeView {
        mint: Pubkey::new_from_array(data[0..32].try_into().expect("classic token mint width")),
        authority: Pubkey::new_from_array(
            data[32..64]
                .try_into()
                .expect("classic token authority width"),
        ),
        amount: u64::from_le_bytes(data[64..72].try_into().expect("classic token amount width")),
    })
}

fn validate_runtime_vault(
    state: &ChannelState,
    channel_key: &Pubkey,
    program_id: &Pubkey,
    vault: &AccountInfo,
    token_program: &AccountInfo,
) -> Result<TokenAccountRuntimeView, ProgramError> {
    require_program_account(token_program, &classic_token_program_id())?;
    let parsed = read_classic_token_account(vault, token_program.key)?;
    let view = VaultAccountView {
        address: *vault.key,
        owner_program: *vault.owner,
        mint: parsed.mint,
        authority: parsed.authority,
        token_program: *token_program.key,
    };
    validate_vault_account(state, channel_key, program_id, &view).map_err(map_vault_error)?;
    Ok(parsed)
}

fn validate_runtime_vault_without_program_meta(
    state: &ChannelState,
    channel_key: &Pubkey,
    program_id: &Pubkey,
    vault: &AccountInfo,
) -> Result<TokenAccountRuntimeView, ProgramError> {
    let classic = classic_token_program_id();
    let parsed = read_classic_token_account(vault, &classic)?;
    let view = VaultAccountView {
        address: *vault.key,
        owner_program: *vault.owner,
        mint: parsed.mint,
        authority: parsed.authority,
        token_program: classic,
    };
    validate_vault_account(state, channel_key, program_id, &view).map_err(map_vault_error)?;
    Ok(parsed)
}

fn require_vault_matches_state(state: &ChannelState, vault_amount: u64) -> ProgramResult {
    let expected = state
        .funded_total
        .checked_sub(state.settled_total)
        .and_then(|value| value.checked_sub(state.refunded_total))
        .ok_or_else(|| custom(ContractErrorCode::ConservationViolation))?;
    if expected != vault_amount {
        return Err(custom(ContractErrorCode::ConservationViolation));
    }
    Ok(())
}

fn require_exact_transfer(
    source_before: u64,
    source_after: u64,
    destination_before: u64,
    destination_after: u64,
    amount: u64,
) -> ProgramResult {
    let expected_source = source_before
        .checked_sub(amount)
        .ok_or_else(|| custom(ContractErrorCode::CheckedArithmeticFailure))?;
    let expected_destination = destination_before
        .checked_add(amount)
        .ok_or_else(|| custom(ContractErrorCode::CheckedArithmeticFailure))?;
    if source_after != expected_source || destination_after != expected_destination {
        return Err(custom(ContractErrorCode::ConservationViolation));
    }
    Ok(())
}

fn token_transfer_checked_instruction(
    source: &Pubkey,
    mint: &Pubkey,
    destination: &Pubkey,
    authority: &Pubkey,
    amount: u64,
    decimals: u8,
) -> Instruction {
    let mut data = Vec::with_capacity(10);
    data.push(TOKEN_INSTRUCTION_TRANSFER_CHECKED);
    data.extend_from_slice(&amount.to_le_bytes());
    data.push(decimals);
    Instruction {
        program_id: classic_token_program_id(),
        accounts: vec![
            AccountMeta::new(*source, false),
            AccountMeta::new_readonly(*mint, false),
            AccountMeta::new(*destination, false),
            AccountMeta::new_readonly(*authority, true),
        ],
        data,
    }
}

fn associated_token_create_idempotent_instruction(
    payer: &Pubkey,
    ata: &Pubkey,
    owner: &Pubkey,
    mint: &Pubkey,
) -> Instruction {
    Instruction {
        program_id: associated_token_program_id(),
        accounts: vec![
            AccountMeta::new(*payer, true),
            AccountMeta::new(*ata, false),
            AccountMeta::new_readonly(*owner, false),
            AccountMeta::new_readonly(*mint, false),
            AccountMeta::new_readonly(system_program::ID, false),
            AccountMeta::new_readonly(classic_token_program_id(), false),
        ],
        data: vec![ATA_INSTRUCTION_CREATE_IDEMPOTENT],
    }
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

fn map_vault_error(error: VaultAccountError) -> ProgramError {
    custom(match error {
        VaultAccountError::ChannelPdaMismatch => ContractErrorCode::WrongPda,
        VaultAccountError::StoredVaultMismatch | VaultAccountError::NonCanonicalVault => {
            ContractErrorCode::WrongVault
        }
        VaultAccountError::WrongOwnerProgram | VaultAccountError::WrongTokenProgram => {
            ContractErrorCode::UnsupportedTokenProgram
        }
        VaultAccountError::WrongMint => ContractErrorCode::WrongMint,
        VaultAccountError::WrongAuthority => ContractErrorCode::WrongVaultAuthority,
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
    use foundry_channel_vault_instruction_contract::{
        encode_binding_nonce_u64, INITIAL_BINDING_NONCE,
    };

    fn state() -> (ChannelState, Pubkey) {
        let program_id = Pubkey::new_unique();
        let sender = Pubkey::new_unique();
        let mint = Pubkey::new_unique();
        let nonce = [7; 32];
        let (channel, bump) = derive_channel_pda(&program_id, &sender, &mint, &nonce);
        let vault = derive_vault_address(&channel, &mint);
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
                vault_token_account: vault,
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
    fn token_transfer_checked_bytes_are_classic_spl_stable() {
        let source = Pubkey::new_unique();
        let mint = Pubkey::new_unique();
        let destination = Pubkey::new_unique();
        let authority = Pubkey::new_unique();
        let instruction = token_transfer_checked_instruction(
            &source,
            &mint,
            &destination,
            &authority,
            1_234_567,
            6,
        );
        assert_eq!(instruction.program_id, classic_token_program_id());
        assert_eq!(instruction.data[0], TOKEN_INSTRUCTION_TRANSFER_CHECKED);
        assert_eq!(u64::from_le_bytes(instruction.data[1..9].try_into().unwrap()), 1_234_567);
        assert_eq!(instruction.data[9], 6);
        assert_eq!(instruction.accounts.len(), 4);
        assert!(instruction.accounts[3].is_signer);
    }

    #[test]
    fn associated_token_create_is_idempotent_and_exact() {
        let payer = Pubkey::new_unique();
        let ata = Pubkey::new_unique();
        let owner = Pubkey::new_unique();
        let mint = Pubkey::new_unique();
        let instruction = associated_token_create_idempotent_instruction(&payer, &ata, &owner, &mint);
        assert_eq!(instruction.program_id, associated_token_program_id());
        assert_eq!(instruction.data, vec![ATA_INSTRUCTION_CREATE_IDEMPOTENT]);
        assert_eq!(instruction.accounts.len(), 6);
        assert!(instruction.accounts[0].is_signer);
    }

    #[test]
    fn vault_accounting_must_match_real_token_balance() {
        let (mut state, _) = state();
        state.settled_total = 15;
        state.refunded_total = 10;
        assert_eq!(require_vault_matches_state(&state, 75), Ok(()));
        assert_eq!(
            require_vault_matches_state(&state, 74),
            Err(custom(ContractErrorCode::ConservationViolation))
        );
    }

    #[test]
    fn exact_transfer_delta_is_checked_both_directions() {
        assert_eq!(require_exact_transfer(100, 60, 5, 45, 40), Ok(()));
        assert_eq!(
            require_exact_transfer(100, 61, 5, 45, 40),
            Err(custom(ContractErrorCode::ConservationViolation))
        );
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

    #[test]
    fn close_account_discriminant_is_not_used_by_v1_finalize() {
        assert_eq!(TOKEN_INSTRUCTION_CLOSE_ACCOUNT, 9);
        let finalize_contract = foundry_channel_vault_instruction_contract::account_contract(
            foundry_channel_vault_instruction_contract::InstructionKind::FinalizeClose,
        );
        assert_eq!(finalize_contract.accounts.len(), 3);
        assert!(finalize_contract.accounts.iter().all(|account| account.name != "token_program"));
    }
}
