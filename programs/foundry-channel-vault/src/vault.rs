use solana_pubkey::Pubkey;
use std::{fmt, str::FromStr};

use crate::ChannelState;

pub const CLASSIC_TOKEN_PROGRAM: &str = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA";
pub const TOKEN_2022_PROGRAM: &str = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb";
pub const ASSOCIATED_TOKEN_PROGRAM: &str = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL";

pub fn classic_token_program_id() -> Pubkey {
    Pubkey::from_str(CLASSIC_TOKEN_PROGRAM).expect("frozen classic SPL Token program ID")
}

pub fn token_2022_program_id() -> Pubkey {
    Pubkey::from_str(TOKEN_2022_PROGRAM).expect("frozen Token-2022 program ID")
}

pub fn associated_token_program_id() -> Pubkey {
    Pubkey::from_str(ASSOCIATED_TOKEN_PROGRAM).expect("frozen associated token account program ID")
}

pub fn derive_vault_address(channel_pda: &Pubkey, mint: &Pubkey) -> Pubkey {
    let token_program = classic_token_program_id();
    Pubkey::find_program_address(
        &[channel_pda.as_ref(), token_program.as_ref(), mint.as_ref()],
        &associated_token_program_id(),
    )
    .0
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct VaultAccountView {
    pub address: Pubkey,
    pub owner_program: Pubkey,
    pub mint: Pubkey,
    pub authority: Pubkey,
    pub token_program: Pubkey,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum VaultAccountError {
    ChannelPdaMismatch,
    StoredVaultMismatch,
    NonCanonicalVault,
    WrongOwnerProgram,
    WrongTokenProgram,
    WrongMint,
    WrongAuthority,
}

impl fmt::Display for VaultAccountError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{self:?}")
    }
}

impl std::error::Error for VaultAccountError {}

pub fn validate_vault_account(
    state: &ChannelState,
    channel_pda: &Pubkey,
    program_id: &Pubkey,
    view: &VaultAccountView,
) -> Result<(), VaultAccountError> {
    if !crate::verify_channel_pda(
        channel_pda,
        state.bump,
        program_id,
        &state.sender,
        &state.mint,
        &state.channel_nonce,
    ) {
        return Err(VaultAccountError::ChannelPdaMismatch);
    }
    if view.address != state.vault_token_account {
        return Err(VaultAccountError::StoredVaultMismatch);
    }
    if view.address != derive_vault_address(channel_pda, &state.mint) {
        return Err(VaultAccountError::NonCanonicalVault);
    }
    let classic = classic_token_program_id();
    if view.owner_program != classic {
        return Err(VaultAccountError::WrongOwnerProgram);
    }
    if view.token_program != classic {
        return Err(VaultAccountError::WrongTokenProgram);
    }
    if view.mint != state.mint {
        return Err(VaultAccountError::WrongMint);
    }
    if view.authority != *channel_pda {
        return Err(VaultAccountError::WrongAuthority);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        ChannelState, EnvironmentCode, NetworkCode, StatusCode, CHANNEL_STATE_RESERVED_BYTES,
        CHANNEL_STATE_VERSION_V1,
    };

    fn fixture() -> (ChannelState, Pubkey, Pubkey, VaultAccountView) {
        let program_id = Pubkey::new_from_array([9; 32]);
        let sender = Pubkey::new_from_array([4; 32]);
        let mint = Pubkey::new_from_array([7; 32]);
        let nonce = [2; 32];
        let (channel_pda, bump) = crate::derive_channel_pda(&program_id, &sender, &mint, &nonce);
        let vault = derive_vault_address(&channel_pda, &mint);
        let state = ChannelState {
            account_version: CHANNEL_STATE_VERSION_V1,
            bump,
            status: StatusCode::Active,
            environment: EnvironmentCode::LocalValidator,
            network: NetworkCode::Solana,
            program_version: 1,
            policy_flags: 0,
            genesis_hash: [1; 32],
            channel_nonce: nonce,
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
            funded_total: 100,
            activated_authorized_total: 40,
            settled_total: 15,
            refunded_total: 0,
            latest_activated_sequence: 3,
            latest_activated_voucher_hash: [10; 32],
            channel_expiry_set: 0,
            channel_expiry: 0,
            voucher_expiry_set: 0,
            voucher_expiry: 0,
            close_requested: 0,
            close_requested_at: 0,
            claim_deadline_set: 0,
            claim_deadline: 0,
            reserved: [0; CHANNEL_STATE_RESERVED_BYTES],
        };
        let view = VaultAccountView {
            address: vault,
            owner_program: classic_token_program_id(),
            mint,
            authority: channel_pda,
            token_program: classic_token_program_id(),
        };
        (state, channel_pda, program_id, view)
    }

    #[test]
    fn accepts_only_exact_classic_vault_relationship() {
        let (state, channel_pda, program_id, view) = fixture();
        assert_eq!(
            validate_vault_account(&state, &channel_pda, &program_id, &view),
            Ok(())
        );
    }

    #[test]
    fn rejects_each_substituted_vault_dimension() {
        let (state, channel_pda, program_id, view) = fixture();

        let cases = [
            (
                VaultAccountView {
                    owner_program: token_2022_program_id(),
                    ..view.clone()
                },
                VaultAccountError::WrongOwnerProgram,
            ),
            (
                VaultAccountView {
                    token_program: token_2022_program_id(),
                    ..view.clone()
                },
                VaultAccountError::WrongTokenProgram,
            ),
            (
                VaultAccountView {
                    mint: Pubkey::new_from_array([11; 32]),
                    ..view.clone()
                },
                VaultAccountError::WrongMint,
            ),
            (
                VaultAccountView {
                    authority: Pubkey::new_from_array([12; 32]),
                    ..view.clone()
                },
                VaultAccountError::WrongAuthority,
            ),
        ];

        for (candidate, expected) in cases {
            assert_eq!(
                validate_vault_account(&state, &channel_pda, &program_id, &candidate),
                Err(expected)
            );
        }

        let wrong_channel = Pubkey::new_from_array([13; 32]);
        assert_eq!(
            validate_vault_account(&state, &wrong_channel, &program_id, &view),
            Err(VaultAccountError::ChannelPdaMismatch)
        );

        let mut wrong_stored_vault = state.clone();
        wrong_stored_vault.vault_token_account = Pubkey::new_from_array([14; 32]);
        assert_eq!(
            validate_vault_account(&wrong_stored_vault, &channel_pda, &program_id, &view),
            Err(VaultAccountError::StoredVaultMismatch)
        );

        let noncanonical = VaultAccountView {
            address: Pubkey::new_from_array([15; 32]),
            ..view
        };
        let mut matching_noncanonical_state = state;
        matching_noncanonical_state.vault_token_account = noncanonical.address;
        assert_eq!(
            validate_vault_account(
                &matching_noncanonical_state,
                &channel_pda,
                &program_id,
                &noncanonical
            ),
            Err(VaultAccountError::NonCanonicalVault)
        );
    }
}
