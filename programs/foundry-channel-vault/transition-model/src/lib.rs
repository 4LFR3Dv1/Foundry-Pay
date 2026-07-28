//! Pure FC-SOL-004 transition model.
//!
//! This crate models projected economic and topology transitions. It contains
//! no Solana entrypoint, `AccountInfo`, CPI, token transfer, RPC, or deployment.

use foundry_channel_vault_account_model::CHANNEL_STATE_SPACE;
use foundry_channel_vault_instruction_contract::{
    MAX_CLAIM_WINDOW_SECONDS, MIN_CLAIM_WINDOW_SECONDS,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fmt;

pub const ZERO_KEY: [u8; 32] = [0; 32];

#[derive(Clone, Copy, Debug, Deserialize, Eq, Hash, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AccountOwnership {
    Absent,
    System,
    ChannelVault,
    ClassicToken,
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Hash, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Lifecycle {
    Uninitialized,
    Active,
    Closing,
    Finalized,
}

#[derive(Clone, Debug, Deserialize, Eq, Hash, PartialEq, Serialize)]
pub struct ModelState {
    pub channel_owner: AccountOwnership,
    pub channel_space: usize,
    pub vault_owner: AccountOwnership,
    pub lifecycle: Lifecycle,
    pub funded: u64,
    pub activated: u64,
    pub settled: u64,
    pub refunded: u64,
    pub latest_sequence: u64,
    pub recipient_bound: bool,
    pub bound_recipient: [u8; 32],
    pub binding_nonce_consumed: bool,
    pub claim_deadline: Option<i64>,
    pub mint: [u8; 32],
    pub vault: [u8; 32],
    pub channel_pda: [u8; 32],
}

impl ModelState {
    pub fn absent() -> Self {
        Self::uninitialized(AccountOwnership::Absent)
    }

    pub fn system_owned() -> Self {
        Self::uninitialized(AccountOwnership::System)
    }

    fn uninitialized(owner: AccountOwnership) -> Self {
        Self {
            channel_owner: owner,
            channel_space: 0,
            vault_owner: AccountOwnership::Absent,
            lifecycle: Lifecycle::Uninitialized,
            funded: 0,
            activated: 0,
            settled: 0,
            refunded: 0,
            latest_sequence: 0,
            recipient_bound: false,
            bound_recipient: ZERO_KEY,
            binding_nonce_consumed: false,
            claim_deadline: None,
            mint: ZERO_KEY,
            vault: ZERO_KEY,
            channel_pda: ZERO_KEY,
        }
    }

    pub fn outstanding(&self) -> Option<u64> {
        self.activated.checked_sub(self.settled)
    }

    pub fn unallocated(&self) -> Option<u64> {
        self.funded
            .checked_sub(self.refunded)?
            .checked_sub(self.activated)
    }

    pub fn invariants_hold(&self) -> bool {
        self.settled <= self.activated
            && self
                .activated
                .checked_add(self.refunded)
                .is_some_and(|reserved| reserved <= self.funded)
            && match self.lifecycle {
                Lifecycle::Uninitialized => {
                    matches!(
                        self.channel_owner,
                        AccountOwnership::Absent | AccountOwnership::System
                    ) && self.channel_space == 0
                        && self.vault_owner == AccountOwnership::Absent
                        && self.funded == 0
                        && self.activated == 0
                        && self.settled == 0
                        && self.refunded == 0
                }
                _ => {
                    self.channel_owner == AccountOwnership::ChannelVault
                        && self.channel_space == CHANNEL_STATE_SPACE
                        && self.vault_owner == AccountOwnership::ClassicToken
                        && self.mint != ZERO_KEY
                        && self.vault != ZERO_KEY
                        && self.channel_pda != ZERO_KEY
                }
            }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum InitializationFault {
    AfterChannelAllocation,
    AfterVaultCreation,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ModelInstruction {
    Initialize {
        mint: [u8; 32],
        vault: [u8; 32],
        channel_pda: [u8; 32],
        injected_fault: Option<InitializationFault>,
    },
    Fund {
        amount: u64,
    },
    Activate {
        sequence: u64,
        cumulative_authorized: u64,
        voucher_expiry: i64,
    },
    BindRecipient {
        recipient: [u8; 32],
    },
    Settle {
        caller: [u8; 32],
        amount: u64,
        obligation_hash: [u8; 32],
        supplied_destination: [u8; 32],
    },
    RequestClose {
        claim_deadline: i64,
    },
    RefundUnallocated {
        amount: u64,
    },
    FinalizeClose,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(tag = "event", rename_all = "snake_case")]
pub enum ModelEvent {
    ChannelInitialized,
    ChannelFunded {
        amount: u64,
    },
    VoucherActivated {
        sequence: u64,
        cumulative_authorized: u64,
    },
    RecipientBound {
        recipient: [u8; 32],
    },
    SettlementExecuted {
        amount: u64,
        #[serde(with = "hex_32")]
        obligation_hash: [u8; 32],
    },
    CloseRequested {
        claim_deadline: i64,
    },
    RefundExecuted {
        amount: u64,
    },
    ChannelFinalized,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Transition {
    pub state: ModelState,
    pub event: ModelEvent,
    pub economic_effect_count: u8,
    pub authority_advancement_count: u8,
    pub lifecycle_transition_count: u8,
    pub settlement_destination: Option<[u8; 32]>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ModelError {
    AlreadyInitialized,
    InvalidInitializationOwner,
    AtomicInitializationFailure,
    Uninitialized,
    Finalized,
    LifecycleViolation,
    ZeroAmount,
    CheckedArithmeticFailure,
    ConservationViolation,
    SequenceReplay,
    ExpiredVoucher,
    BindingNonceConsumed,
    InvalidRecipient,
    RecipientNotBound,
    RecipientSubstitution,
    InvalidClaimWindow,
    ClaimWindowOverflow,
    ClaimWindowOpen,
    OutstandingRight,
    UnallocatedCapacity,
}

impl fmt::Display for ModelError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{self:?}")
    }
}

impl std::error::Error for ModelError {}

pub fn canonical_recipient_ata(recipient: [u8; 32], mint: [u8; 32]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(b"foundry.channels.model.canonical-ata.v1");
    hasher.update(recipient);
    hasher.update(mint);
    hasher.finalize().into()
}

pub fn apply(
    state: &ModelState,
    instruction: &ModelInstruction,
    now: i64,
) -> Result<Transition, ModelError> {
    if !state.invariants_hold() {
        return Err(ModelError::ConservationViolation);
    }
    if state.lifecycle == Lifecycle::Finalized {
        return Err(ModelError::Finalized);
    }

    match instruction {
        ModelInstruction::Initialize {
            mint,
            vault,
            channel_pda,
            injected_fault,
        } => initialize(state, *mint, *vault, *channel_pda, *injected_fault),
        _ if state.lifecycle == Lifecycle::Uninitialized => Err(ModelError::Uninitialized),
        ModelInstruction::Fund { amount } => fund(state, *amount),
        ModelInstruction::Activate {
            sequence,
            cumulative_authorized,
            voucher_expiry,
        } => activate(
            state,
            *sequence,
            *cumulative_authorized,
            *voucher_expiry,
            now,
        ),
        ModelInstruction::BindRecipient { recipient } => bind(state, *recipient, now),
        ModelInstruction::Settle {
            caller: _,
            amount,
            obligation_hash,
            supplied_destination,
        } => settle(state, *amount, *obligation_hash, *supplied_destination, now),
        ModelInstruction::RequestClose { claim_deadline } => {
            request_close(state, *claim_deadline, now)
        }
        ModelInstruction::RefundUnallocated { amount } => refund(state, *amount, now),
        ModelInstruction::FinalizeClose => finalize(state, now),
    }
}

fn initialize(
    state: &ModelState,
    mint: [u8; 32],
    vault: [u8; 32],
    channel_pda: [u8; 32],
    injected_fault: Option<InitializationFault>,
) -> Result<Transition, ModelError> {
    if state.lifecycle != Lifecycle::Uninitialized {
        return Err(ModelError::AlreadyInitialized);
    }
    if !matches!(
        state.channel_owner,
        AccountOwnership::Absent | AccountOwnership::System
    ) || state.channel_space != 0
        || state.vault_owner != AccountOwnership::Absent
    {
        return Err(ModelError::InvalidInitializationOwner);
    }
    if mint == ZERO_KEY || vault == ZERO_KEY || channel_pda == ZERO_KEY {
        return Err(ModelError::InvalidInitializationOwner);
    }
    if injected_fault.is_some() {
        return Err(ModelError::AtomicInitializationFailure);
    }
    let mut next = state.clone();
    next.channel_owner = AccountOwnership::ChannelVault;
    next.channel_space = CHANNEL_STATE_SPACE;
    next.vault_owner = AccountOwnership::ClassicToken;
    next.lifecycle = Lifecycle::Active;
    next.mint = mint;
    next.vault = vault;
    next.channel_pda = channel_pda;
    success(state, next, ModelEvent::ChannelInitialized, 0, 1, None)
}

fn fund(state: &ModelState, amount: u64) -> Result<Transition, ModelError> {
    require_phase(state, &[Lifecycle::Active])?;
    require_positive(amount)?;
    let mut next = state.clone();
    next.funded = next
        .funded
        .checked_add(amount)
        .ok_or(ModelError::CheckedArithmeticFailure)?;
    success(
        state,
        next,
        ModelEvent::ChannelFunded { amount },
        1,
        0,
        None,
    )
}

fn activate(
    state: &ModelState,
    sequence: u64,
    cumulative: u64,
    voucher_expiry: i64,
    now: i64,
) -> Result<Transition, ModelError> {
    require_active_or_closing_open(state, now)?;
    if voucher_expiry <= now {
        return Err(ModelError::ExpiredVoucher);
    }
    if sequence <= state.latest_sequence {
        return Err(ModelError::SequenceReplay);
    }
    if cumulative < state.activated {
        return Err(ModelError::ConservationViolation);
    }
    let available = state
        .funded
        .checked_sub(state.refunded)
        .ok_or(ModelError::ConservationViolation)?;
    if cumulative > available {
        return Err(ModelError::ConservationViolation);
    }
    let mut next = state.clone();
    next.activated = cumulative;
    next.latest_sequence = sequence;
    success(
        state,
        next,
        ModelEvent::VoucherActivated {
            sequence,
            cumulative_authorized: cumulative,
        },
        u8::from(cumulative != state.activated),
        1,
        None,
    )
}

fn bind(state: &ModelState, recipient: [u8; 32], now: i64) -> Result<Transition, ModelError> {
    require_active_or_closing_open(state, now)?;
    if state.recipient_bound || state.binding_nonce_consumed {
        return Err(ModelError::BindingNonceConsumed);
    }
    if recipient == ZERO_KEY {
        return Err(ModelError::InvalidRecipient);
    }
    let mut next = state.clone();
    next.recipient_bound = true;
    next.bound_recipient = recipient;
    next.binding_nonce_consumed = true;
    success(
        state,
        next,
        ModelEvent::RecipientBound { recipient },
        0,
        1,
        None,
    )
}

fn settle(
    state: &ModelState,
    amount: u64,
    obligation_hash: [u8; 32],
    supplied_destination: [u8; 32],
    now: i64,
) -> Result<Transition, ModelError> {
    require_settle_phase(state, now)?;
    require_positive(amount)?;
    if !state.recipient_bound {
        return Err(ModelError::RecipientNotBound);
    }
    let destination = canonical_recipient_ata(state.bound_recipient, state.mint);
    if supplied_destination != destination {
        return Err(ModelError::RecipientSubstitution);
    }
    let outstanding = state
        .outstanding()
        .ok_or(ModelError::ConservationViolation)?;
    if amount > outstanding {
        return Err(ModelError::OutstandingRight);
    }
    let mut next = state.clone();
    next.settled = next
        .settled
        .checked_add(amount)
        .ok_or(ModelError::CheckedArithmeticFailure)?;
    success(
        state,
        next,
        ModelEvent::SettlementExecuted {
            amount,
            obligation_hash,
        },
        1,
        0,
        Some(destination),
    )
}

fn request_close(
    state: &ModelState,
    claim_deadline: i64,
    now: i64,
) -> Result<Transition, ModelError> {
    require_phase(state, &[Lifecycle::Active])?;
    let minimum = now
        .checked_add(MIN_CLAIM_WINDOW_SECONDS)
        .ok_or(ModelError::ClaimWindowOverflow)?;
    let maximum = now
        .checked_add(MAX_CLAIM_WINDOW_SECONDS)
        .ok_or(ModelError::ClaimWindowOverflow)?;
    if claim_deadline < minimum || claim_deadline > maximum {
        return Err(ModelError::InvalidClaimWindow);
    }
    let mut next = state.clone();
    next.lifecycle = Lifecycle::Closing;
    next.claim_deadline = Some(claim_deadline);
    success(
        state,
        next,
        ModelEvent::CloseRequested { claim_deadline },
        0,
        1,
        None,
    )
}

fn refund(state: &ModelState, amount: u64, now: i64) -> Result<Transition, ModelError> {
    require_closing_frozen(state, now)?;
    require_positive(amount)?;
    let unallocated = state
        .unallocated()
        .ok_or(ModelError::ConservationViolation)?;
    if amount > unallocated {
        return Err(ModelError::UnallocatedCapacity);
    }
    let mut next = state.clone();
    next.refunded = next
        .refunded
        .checked_add(amount)
        .ok_or(ModelError::CheckedArithmeticFailure)?;
    success(
        state,
        next,
        ModelEvent::RefundExecuted { amount },
        1,
        0,
        None,
    )
}

fn finalize(state: &ModelState, now: i64) -> Result<Transition, ModelError> {
    require_closing_frozen(state, now)?;
    if state.outstanding() != Some(0) {
        return Err(ModelError::OutstandingRight);
    }
    if state.unallocated() != Some(0) {
        return Err(ModelError::UnallocatedCapacity);
    }
    let mut next = state.clone();
    next.lifecycle = Lifecycle::Finalized;
    success(state, next, ModelEvent::ChannelFinalized, 0, 1, None)
}

fn require_positive(amount: u64) -> Result<(), ModelError> {
    if amount == 0 {
        Err(ModelError::ZeroAmount)
    } else {
        Ok(())
    }
}

fn require_phase(state: &ModelState, allowed: &[Lifecycle]) -> Result<(), ModelError> {
    if allowed.contains(&state.lifecycle) {
        Ok(())
    } else {
        Err(ModelError::LifecycleViolation)
    }
}

fn require_active_or_closing_open(state: &ModelState, now: i64) -> Result<(), ModelError> {
    match state.lifecycle {
        Lifecycle::Active => Ok(()),
        Lifecycle::Closing if state.claim_deadline.is_some_and(|deadline| now < deadline) => Ok(()),
        _ => Err(ModelError::LifecycleViolation),
    }
}

fn require_settle_phase(state: &ModelState, _now: i64) -> Result<(), ModelError> {
    match state.lifecycle {
        Lifecycle::Active | Lifecycle::Closing => Ok(()),
        _ => Err(ModelError::LifecycleViolation),
    }
}

fn require_closing_frozen(state: &ModelState, now: i64) -> Result<(), ModelError> {
    match (state.lifecycle, state.claim_deadline) {
        (Lifecycle::Closing, Some(deadline)) if now >= deadline => Ok(()),
        (Lifecycle::Closing, Some(_)) => Err(ModelError::ClaimWindowOpen),
        _ => Err(ModelError::LifecycleViolation),
    }
}

fn success(
    previous: &ModelState,
    next: ModelState,
    event: ModelEvent,
    economic_effect_count: u8,
    authority_advancement_count: u8,
    settlement_destination: Option<[u8; 32]>,
) -> Result<Transition, ModelError> {
    if !next.invariants_hold()
        || next.funded < previous.funded
        || next.activated < previous.activated
        || next.settled < previous.settled
        || next.refunded < previous.refunded
    {
        return Err(ModelError::ConservationViolation);
    }
    Ok(Transition {
        lifecycle_transition_count: u8::from(next.lifecycle != previous.lifecycle),
        state: next,
        event,
        economic_effect_count,
        authority_advancement_count,
        settlement_destination,
    })
}

mod hex_32 {
    use serde::Serializer;

    pub fn serialize<S>(value: &[u8; 32], serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&hex::encode(value))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn key(value: u8) -> [u8; 32] {
        [value; 32]
    }

    fn initialized() -> ModelState {
        apply(
            &ModelState::absent(),
            &ModelInstruction::Initialize {
                mint: key(1),
                vault: key(2),
                channel_pda: key(3),
                injected_fault: None,
            },
            0,
        )
        .unwrap()
        .state
    }

    fn funded_bound_activated() -> ModelState {
        let state = apply(&initialized(), &ModelInstruction::Fund { amount: 100 }, 0)
            .unwrap()
            .state;
        let state = apply(
            &state,
            &ModelInstruction::Activate {
                sequence: 1,
                cumulative_authorized: 40,
                voucher_expiry: 10_000,
            },
            0,
        )
        .unwrap()
        .state;
        apply(
            &state,
            &ModelInstruction::BindRecipient { recipient: key(9) },
            0,
        )
        .unwrap()
        .state
    }

    #[test]
    fn initialization_is_an_atomic_owner_transition() {
        for owner in [AccountOwnership::Absent, AccountOwnership::System] {
            let state = if owner == AccountOwnership::Absent {
                ModelState::absent()
            } else {
                ModelState::system_owned()
            };
            for fault in [
                InitializationFault::AfterChannelAllocation,
                InitializationFault::AfterVaultCreation,
            ] {
                let result = apply(
                    &state,
                    &ModelInstruction::Initialize {
                        mint: key(1),
                        vault: key(2),
                        channel_pda: key(3),
                        injected_fault: Some(fault),
                    },
                    0,
                );
                assert_eq!(result, Err(ModelError::AtomicInitializationFailure));
                assert_eq!(state.channel_owner, owner);
                assert_eq!(state.vault_owner, AccountOwnership::Absent);
            }
            let next = apply(
                &state,
                &ModelInstruction::Initialize {
                    mint: key(1),
                    vault: key(2),
                    channel_pda: key(3),
                    injected_fault: None,
                },
                0,
            )
            .unwrap()
            .state;
            assert_eq!(next.channel_owner, AccountOwnership::ChannelVault);
            assert_eq!(next.vault_owner, AccountOwnership::ClassicToken);
            assert_eq!(next.channel_space, CHANNEL_STATE_SPACE);
        }
    }

    #[test]
    fn permissionless_settlement_is_caller_and_correlation_independent() {
        let state = funded_bound_activated();
        let destination = canonical_recipient_ata(state.bound_recipient, state.mint);
        let a = apply(
            &state,
            &ModelInstruction::Settle {
                caller: key(10),
                amount: 25,
                obligation_hash: key(11),
                supplied_destination: destination,
            },
            1,
        )
        .unwrap();
        let b = apply(
            &state,
            &ModelInstruction::Settle {
                caller: key(12),
                amount: 25,
                obligation_hash: key(13),
                supplied_destination: destination,
            },
            1,
        )
        .unwrap();
        assert_eq!(a.state, b.state);
        assert_eq!(a.settlement_destination, b.settlement_destination);
        assert_ne!(a.event, b.event);
    }

    #[test]
    fn claim_window_boundaries_and_exclusive_deadline_hold() {
        let state = initialized();
        assert!(apply(
            &state,
            &ModelInstruction::RequestClose {
                claim_deadline: 1_000 + MIN_CLAIM_WINDOW_SECONDS - 1,
            },
            1_000,
        )
        .is_err());
        for delta in [MIN_CLAIM_WINDOW_SECONDS, MAX_CLAIM_WINDOW_SECONDS] {
            assert!(apply(
                &state,
                &ModelInstruction::RequestClose {
                    claim_deadline: 1_000 + delta,
                },
                1_000,
            )
            .is_ok());
        }
        assert!(apply(
            &state,
            &ModelInstruction::RequestClose {
                claim_deadline: 1_000 + MAX_CLAIM_WINDOW_SECONDS + 1,
            },
            1_000,
        )
        .is_err());
        assert_eq!(
            apply(
                &state,
                &ModelInstruction::RequestClose {
                    claim_deadline: i64::MAX,
                },
                i64::MAX,
            ),
            Err(ModelError::ClaimWindowOverflow)
        );

        let closing = apply(
            &funded_bound_activated(),
            &ModelInstruction::RequestClose {
                claim_deadline: 1_000,
            },
            0,
        )
        .unwrap()
        .state;
        assert!(apply(
            &closing,
            &ModelInstruction::Activate {
                sequence: 2,
                cumulative_authorized: 50,
                voucher_expiry: 2_000,
            },
            999,
        )
        .is_ok());
        assert!(apply(
            &closing,
            &ModelInstruction::Activate {
                sequence: 2,
                cumulative_authorized: 50,
                voucher_expiry: 2_000,
            },
            1_000,
        )
        .is_err());
    }

    #[test]
    fn close_refund_settle_finalize_preserves_activated_rights() {
        let state = funded_bound_activated();
        let closing = apply(
            &state,
            &ModelInstruction::RequestClose {
                claim_deadline: 1_000,
            },
            0,
        )
        .unwrap()
        .state;
        let refunded = apply(
            &closing,
            &ModelInstruction::RefundUnallocated { amount: 60 },
            1_000,
        )
        .unwrap()
        .state;
        assert_eq!(refunded.activated, 40);
        assert_eq!(refunded.outstanding(), Some(40));
        let destination = canonical_recipient_ata(refunded.bound_recipient, refunded.mint);
        let settled = apply(
            &refunded,
            &ModelInstruction::Settle {
                caller: key(20),
                amount: 40,
                obligation_hash: key(21),
                supplied_destination: destination,
            },
            1_001,
        )
        .unwrap()
        .state;
        let finalized = apply(&settled, &ModelInstruction::FinalizeClose, 1_001).unwrap();
        assert_eq!(finalized.state.lifecycle, Lifecycle::Finalized);
        assert!(apply(
            &finalized.state,
            &ModelInstruction::Fund { amount: 1 },
            1_002
        )
        .is_err());
    }

    proptest! {
        #![proptest_config(ProptestConfig {
            cases: 512,
            max_shrink_iters: 4096,
            .. ProptestConfig::default()
        })]

        #[test]
        fn arbitrary_valid_economic_path_preserves_invariants(
            funding in 1u64..1_000_000,
            activated_fraction in 0u16..=1000,
            settled_fraction in 0u16..=1000,
            refund_fraction in 0u16..=1000,
            caller in any::<[u8; 32]>(),
            obligation in any::<[u8; 32]>(),
        ) {
            let mut state = initialized();
            state = apply(&state, &ModelInstruction::Fund { amount: funding }, 0).unwrap().state;
            let activated = ((funding as u128 * activated_fraction as u128) / 1000) as u64;
            state = apply(
                &state,
                &ModelInstruction::Activate {
                    sequence: 1,
                    cumulative_authorized: activated,
                    voucher_expiry: 10_000,
                },
                0,
            ).unwrap().state;
            state = apply(
                &state,
                &ModelInstruction::BindRecipient { recipient: key(9) },
                0,
            ).unwrap().state;
            let settle_amount = ((activated as u128 * settled_fraction as u128) / 1000) as u64;
            if settle_amount > 0 {
                let destination = canonical_recipient_ata(state.bound_recipient, state.mint);
                state = apply(
                    &state,
                    &ModelInstruction::Settle {
                        caller,
                        amount: settle_amount,
                        obligation_hash: obligation,
                        supplied_destination: destination,
                    },
                    1,
                ).unwrap().state;
            }
            state = apply(
                &state,
                &ModelInstruction::RequestClose { claim_deadline: 1_000 },
                0,
            ).unwrap().state;
            let capacity = state.unallocated().unwrap();
            let refund_amount = ((capacity as u128 * refund_fraction as u128) / 1000) as u64;
            if refund_amount > 0 {
                state = apply(
                    &state,
                    &ModelInstruction::RefundUnallocated { amount: refund_amount },
                    1_000,
                ).unwrap().state;
            }
            prop_assert!(state.invariants_hold());
            prop_assert!(state.settled <= state.activated);
            prop_assert!(state.activated + state.refunded <= state.funded);
        }

        #[test]
        fn rejected_settlement_never_changes_input_state(
            amount in any::<u64>(),
            caller in any::<[u8; 32]>(),
            obligation in any::<[u8; 32]>(),
            wrong_destination in any::<[u8; 32]>(),
        ) {
            let state = funded_bound_activated();
            let expected = canonical_recipient_ata(state.bound_recipient, state.mint);
            prop_assume!(wrong_destination != expected || amount == 0 || amount > 40);
            let before = state.clone();
            let result = apply(
                &state,
                &ModelInstruction::Settle {
                    caller,
                    amount,
                    obligation_hash: obligation,
                    supplied_destination: wrong_destination,
                },
                1,
            );
            prop_assert!(result.is_err());
            prop_assert_eq!(state, before);
        }

        #[test]
        fn arbitrary_instruction_sequences_preserve_invariants_or_reject_atomically(
            actions in prop::collection::vec(
                (0u8..8, any::<u64>(), any::<i64>(), any::<[u8; 32]>()),
                1..64,
            ),
        ) {
            let mut state = ModelState::absent();
            for (kind, value, time, material) in actions {
                let destination = if state.recipient_bound {
                    canonical_recipient_ata(state.bound_recipient, state.mint)
                } else {
                    material
                };
                let instruction = match kind {
                    0 => ModelInstruction::Initialize {
                        mint: key(1),
                        vault: key(2),
                        channel_pda: key(3),
                        injected_fault: None,
                    },
                    1 => ModelInstruction::Fund { amount: value },
                    2 => ModelInstruction::Activate {
                        sequence: value,
                        cumulative_authorized: value,
                        voucher_expiry: time,
                    },
                    3 => ModelInstruction::BindRecipient { recipient: material },
                    4 => ModelInstruction::Settle {
                        caller: material,
                        amount: value,
                        obligation_hash: key(kind),
                        supplied_destination: destination,
                    },
                    5 => ModelInstruction::RequestClose {
                        claim_deadline: time,
                    },
                    6 => ModelInstruction::RefundUnallocated { amount: value },
                    _ => ModelInstruction::FinalizeClose,
                };
                let before = state.clone();
                match apply(&state, &instruction, time) {
                    Ok(transition) => {
                        prop_assert!(transition.state.invariants_hold());
                        prop_assert!(transition.state.funded >= before.funded);
                        prop_assert!(transition.state.activated >= before.activated);
                        prop_assert!(transition.state.settled >= before.settled);
                        prop_assert!(transition.state.refunded >= before.refunded);
                        state = transition.state;
                    }
                    Err(_) => {
                        prop_assert_eq!(&state, &before);
                    }
                }
            }
        }
    }
}
