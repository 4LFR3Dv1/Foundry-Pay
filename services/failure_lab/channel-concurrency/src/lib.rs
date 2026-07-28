//! Offline FC-SEC-004 concurrency model.
//!
//! This crate wraps the independent FC-SOL-004 transition oracle with
//! versioned snapshot preparation, conditional commit, duplicate protection,
//! commit-time revalidation, and serial witness replay.

use foundry_channel_vault_transition_model::{
    apply, ModelError, ModelEvent, ModelInstruction, ModelState, Transition,
};
use serde::Serialize;
use std::{collections::BTreeSet, fmt};

pub type OperationId = [u8; 32];

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct VersionedState {
    pub version: u64,
    pub state: ModelState,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CandidateTransition {
    pub read_version: u64,
    pub instruction_id: OperationId,
    pub operation: ModelInstruction,
    pub prepared_at: i64,
    pub projected: Transition,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct CommitRecord {
    #[serde(with = "hex_32")]
    pub instruction_id: OperationId,
    #[serde(skip)]
    pub operation: Option<ModelInstruction>,
    pub prepared_at: i64,
    pub committed_at: i64,
    pub version_before: u64,
    pub version_after: u64,
    pub event: ModelEvent,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CommitOutcome {
    pub record: CommitRecord,
    pub state: VersionedState,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ConcurrencyError {
    Model(ModelError),
    StaleSnapshot,
    DuplicateOperation,
    VersionOverflow,
    MissingWitnessOperation,
    SerialWitnessMismatch,
}

impl fmt::Display for ConcurrencyError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{self:?}")
    }
}

impl std::error::Error for ConcurrencyError {}

impl From<ModelError> for ConcurrencyError {
    fn from(value: ModelError) -> Self {
        Self::Model(value)
    }
}

#[derive(Clone, Debug)]
pub struct LinearizationHarness {
    initial_state: ModelState,
    current: VersionedState,
    accepted_operation_ids: BTreeSet<OperationId>,
    history: Vec<CommitRecord>,
}

impl LinearizationHarness {
    pub fn new(initial_state: ModelState) -> Result<Self, ConcurrencyError> {
        if !initial_state.invariants_hold() {
            return Err(ConcurrencyError::Model(ModelError::ConservationViolation));
        }
        Ok(Self {
            initial_state: initial_state.clone(),
            current: VersionedState {
                version: 0,
                state: initial_state,
            },
            accepted_operation_ids: BTreeSet::new(),
            history: Vec::new(),
        })
    }

    pub fn snapshot(&self) -> VersionedState {
        self.current.clone()
    }

    pub fn history(&self) -> &[CommitRecord] {
        &self.history
    }

    pub fn accepted_operation_count(&self) -> usize {
        self.accepted_operation_ids.len()
    }

    pub fn prepare(
        &self,
        instruction_id: OperationId,
        operation: ModelInstruction,
        observed_time: i64,
    ) -> Result<CandidateTransition, ConcurrencyError> {
        if self.accepted_operation_ids.contains(&instruction_id) {
            return Err(ConcurrencyError::DuplicateOperation);
        }
        let projected = apply(&self.current.state, &operation, observed_time)?;
        Ok(CandidateTransition {
            read_version: self.current.version,
            instruction_id,
            operation,
            prepared_at: observed_time,
            projected,
        })
    }

    pub fn commit(
        &mut self,
        candidate: CandidateTransition,
        authoritative_time: i64,
    ) -> Result<CommitOutcome, ConcurrencyError> {
        if self
            .accepted_operation_ids
            .contains(&candidate.instruction_id)
        {
            return Err(ConcurrencyError::DuplicateOperation);
        }
        if candidate.read_version != self.current.version {
            return Err(ConcurrencyError::StaleSnapshot);
        }

        // The FC-SOL-004 oracle is intentionally invoked again. Preparation is
        // never authority, and time-sensitive guards use commit time.
        let committed = apply(
            &self.current.state,
            &candidate.operation,
            authoritative_time,
        )?;
        let next_version = self
            .current
            .version
            .checked_add(1)
            .ok_or(ConcurrencyError::VersionOverflow)?;
        let record = CommitRecord {
            instruction_id: candidate.instruction_id,
            operation: Some(candidate.operation),
            prepared_at: candidate.prepared_at,
            committed_at: authoritative_time,
            version_before: self.current.version,
            version_after: next_version,
            event: committed.event.clone(),
        };
        self.current = VersionedState {
            version: next_version,
            state: committed.state,
        };
        self.accepted_operation_ids.insert(candidate.instruction_id);
        self.history.push(record.clone());
        Ok(CommitOutcome {
            record,
            state: self.current.clone(),
        })
    }

    pub fn verify_serial_witness(&self) -> Result<(), ConcurrencyError> {
        let mut replayed = self.initial_state.clone();
        let mut version = 0u64;
        let mut ids = BTreeSet::new();
        for record in &self.history {
            if record.version_before != version
                || record.version_after != version + 1
                || !ids.insert(record.instruction_id)
            {
                return Err(ConcurrencyError::SerialWitnessMismatch);
            }
            let operation = record
                .operation
                .as_ref()
                .ok_or(ConcurrencyError::MissingWitnessOperation)?;
            let transition = apply(&replayed, operation, record.committed_at)?;
            if transition.event != record.event {
                return Err(ConcurrencyError::SerialWitnessMismatch);
            }
            replayed = transition.state;
            version += 1;
        }
        if replayed != self.current.state
            || version != self.current.version
            || ids != self.accepted_operation_ids
        {
            return Err(ConcurrencyError::SerialWitnessMismatch);
        }
        Ok(())
    }
}

pub fn modeled_vault_balance(state: &ModelState) -> Result<u64, ConcurrencyError> {
    state
        .funded
        .checked_sub(state.refunded)
        .and_then(|value| value.checked_sub(state.settled))
        .ok_or(ConcurrencyError::Model(ModelError::ConservationViolation))
}

pub fn vault_conservation_holds(state: &ModelState) -> bool {
    modeled_vault_balance(state)
        .ok()
        .and_then(|vault| vault.checked_add(state.settled))
        .and_then(|value| value.checked_add(state.refunded))
        == Some(state.funded)
}

mod hex_32 {
    use serde::Serializer;

    pub fn serialize<S>(value: &[u8; 32], serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&hex(value))
    }

    fn hex(value: &[u8]) -> String {
        const DIGITS: &[u8; 16] = b"0123456789abcdef";
        let mut output = String::with_capacity(value.len() * 2);
        for byte in value {
            output.push(DIGITS[(byte >> 4) as usize] as char);
            output.push(DIGITS[(byte & 0x0f) as usize] as char);
        }
        output
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use foundry_channel_vault_transition_model::{
        canonical_recipient_ata, Lifecycle, ModelInstruction,
    };
    use proptest::prelude::*;

    fn key(value: u8) -> [u8; 32] {
        [value; 32]
    }

    fn apply_ok(state: &ModelState, operation: ModelInstruction, now: i64) -> ModelState {
        apply(state, &operation, now).unwrap().state
    }

    fn active(funded: u64, activated: u64, settled: u64) -> ModelState {
        let mut state = apply_ok(
            &ModelState::absent(),
            ModelInstruction::Initialize {
                mint: key(1),
                vault: key(2),
                channel_pda: key(3),
                injected_fault: None,
            },
            0,
        );
        state = apply_ok(&state, ModelInstruction::Fund { amount: funded }, 0);
        state = apply_ok(
            &state,
            ModelInstruction::Activate {
                sequence: 1,
                cumulative_authorized: activated,
                voucher_expiry: 10_000,
            },
            0,
        );
        state = apply_ok(
            &state,
            ModelInstruction::BindRecipient { recipient: key(9) },
            0,
        );
        if settled > 0 {
            let destination = canonical_recipient_ata(state.bound_recipient, state.mint);
            state = apply_ok(
                &state,
                ModelInstruction::Settle {
                    caller: key(10),
                    amount: settled,
                    obligation_hash: key(11),
                    supplied_destination: destination,
                },
                0,
            );
        }
        state
    }

    fn closing(funded: u64, activated: u64, settled: u64, deadline: i64) -> ModelState {
        apply_ok(
            &active(funded, activated, settled),
            ModelInstruction::RequestClose {
                claim_deadline: deadline,
            },
            0,
        )
    }

    fn settlement(state: &ModelState, caller: u8, amount: u64) -> ModelInstruction {
        ModelInstruction::Settle {
            caller: key(caller),
            amount,
            obligation_hash: key(caller.wrapping_add(1)),
            supplied_destination: canonical_recipient_ata(state.bound_recipient, state.mint),
        }
    }

    #[test]
    fn oversubscribed_settlements_from_one_snapshot_cannot_both_commit() {
        let state = active(100, 40, 0);
        let mut harness = LinearizationHarness::new(state).unwrap();
        let a = harness
            .prepare(key(20), settlement(&harness.snapshot().state, 1, 30), 1)
            .unwrap();
        let b = harness
            .prepare(key(21), settlement(&harness.snapshot().state, 2, 30), 1)
            .unwrap();
        harness.commit(a, 1).unwrap();
        let after_first = harness.snapshot();
        assert_eq!(harness.commit(b, 1), Err(ConcurrencyError::StaleSnapshot));
        assert_eq!(harness.snapshot(), after_first);
        assert_eq!(harness.snapshot().state.settled, 30);
        assert_eq!(harness.accepted_operation_count(), 1);
        assert_eq!(harness.verify_serial_witness(), Ok(()));
    }

    #[test]
    fn safe_partial_settlements_require_explicit_repreparation() {
        let state = active(100, 40, 0);
        let mut harness = LinearizationHarness::new(state).unwrap();
        let a = harness
            .prepare(key(20), settlement(&harness.snapshot().state, 1, 10), 1)
            .unwrap();
        let stale_b = harness
            .prepare(key(21), settlement(&harness.snapshot().state, 2, 30), 1)
            .unwrap();
        harness.commit(a, 1).unwrap();
        assert_eq!(
            harness.commit(stale_b, 1),
            Err(ConcurrencyError::StaleSnapshot)
        );
        let fresh_b = harness
            .prepare(key(21), settlement(&harness.snapshot().state, 2, 30), 2)
            .unwrap();
        harness.commit(fresh_b, 2).unwrap();
        assert_eq!(harness.snapshot().state.settled, 40);
        assert_eq!(harness.snapshot().version, 2);
        assert_eq!(harness.verify_serial_witness(), Ok(()));
    }

    #[test]
    fn duplicate_operation_id_has_one_economic_effect() {
        let state = active(100, 40, 0);
        let mut harness = LinearizationHarness::new(state).unwrap();
        let operation = settlement(&harness.snapshot().state, 1, 20);
        let a = harness.prepare(key(20), operation.clone(), 1).unwrap();
        let duplicate = harness.prepare(key(20), operation, 1).unwrap();
        harness.commit(a, 1).unwrap();
        let snapshot = harness.snapshot();
        assert_eq!(
            harness.commit(duplicate, 1),
            Err(ConcurrencyError::DuplicateOperation)
        );
        assert_eq!(harness.snapshot(), snapshot);
        assert_eq!(harness.snapshot().state.settled, 20);
    }

    #[test]
    fn refund_and_settlement_linearize_after_stale_repreparation() {
        let state = closing(100, 40, 0, 900);
        let mut harness = LinearizationHarness::new(state).unwrap();
        let refund = harness
            .prepare(
                key(30),
                ModelInstruction::RefundUnallocated { amount: 60 },
                900,
            )
            .unwrap();
        let stale_settle = harness
            .prepare(key(31), settlement(&harness.snapshot().state, 2, 40), 900)
            .unwrap();
        harness.commit(refund, 900).unwrap();
        assert_eq!(
            harness.commit(stale_settle, 900),
            Err(ConcurrencyError::StaleSnapshot)
        );
        let settle = harness
            .prepare(key(31), settlement(&harness.snapshot().state, 2, 40), 901)
            .unwrap();
        harness.commit(settle, 901).unwrap();
        let state = &harness.snapshot().state;
        assert_eq!((state.refunded, state.settled), (60, 40));
        assert!(vault_conservation_holds(state));
        assert_eq!(harness.verify_serial_witness(), Ok(()));
    }

    #[test]
    fn activation_prepared_before_deadline_is_revalidated_at_commit() {
        let state = closing(100, 40, 0, 900);
        let mut harness = LinearizationHarness::new(state).unwrap();
        let activation = harness
            .prepare(
                key(40),
                ModelInstruction::Activate {
                    sequence: 2,
                    cumulative_authorized: 70,
                    voucher_expiry: 2_000,
                },
                899,
            )
            .unwrap();
        let before = harness.snapshot();
        assert_eq!(
            harness.commit(activation, 900),
            Err(ConcurrencyError::Model(ModelError::LifecycleViolation))
        );
        assert_eq!(harness.snapshot(), before);
    }

    #[test]
    fn activation_and_close_have_a_serial_witness() {
        let state = active(100, 40, 0);
        let mut harness = LinearizationHarness::new(state).unwrap();
        let close = harness
            .prepare(
                key(50),
                ModelInstruction::RequestClose {
                    claim_deadline: 900,
                },
                0,
            )
            .unwrap();
        let stale_activation = harness
            .prepare(
                key(51),
                ModelInstruction::Activate {
                    sequence: 2,
                    cumulative_authorized: 70,
                    voucher_expiry: 2_000,
                },
                0,
            )
            .unwrap();
        harness.commit(close, 0).unwrap();
        assert_eq!(
            harness.commit(stale_activation, 1),
            Err(ConcurrencyError::StaleSnapshot)
        );
        let activation = harness
            .prepare(
                key(51),
                ModelInstruction::Activate {
                    sequence: 2,
                    cumulative_authorized: 70,
                    voucher_expiry: 2_000,
                },
                1,
            )
            .unwrap();
        harness.commit(activation, 1).unwrap();
        assert_eq!(harness.snapshot().state.activated, 70);
        assert_eq!(harness.verify_serial_witness(), Ok(()));
    }

    #[test]
    fn settlement_then_finalize_requires_fresh_snapshot() {
        let state = closing(40, 40, 0, 900);
        let mut harness = LinearizationHarness::new(state).unwrap();
        assert!(matches!(
            harness.prepare(key(60), ModelInstruction::FinalizeClose, 900),
            Err(ConcurrencyError::Model(ModelError::OutstandingRight))
        ));
        let settle = harness
            .prepare(key(61), settlement(&harness.snapshot().state, 2, 40), 900)
            .unwrap();
        harness.commit(settle, 900).unwrap();
        let finalize = harness
            .prepare(key(60), ModelInstruction::FinalizeClose, 901)
            .unwrap();
        harness.commit(finalize, 901).unwrap();
        assert_eq!(harness.snapshot().state.lifecycle, Lifecycle::Finalized);
        assert_eq!(harness.verify_serial_witness(), Ok(()));
    }

    #[test]
    fn refund_then_finalize_requires_fresh_snapshot() {
        let state = closing(100, 40, 40, 900);
        let mut harness = LinearizationHarness::new(state).unwrap();
        assert!(matches!(
            harness.prepare(key(70), ModelInstruction::FinalizeClose, 900),
            Err(ConcurrencyError::Model(ModelError::UnallocatedCapacity))
        ));
        let refund = harness
            .prepare(
                key(71),
                ModelInstruction::RefundUnallocated { amount: 60 },
                900,
            )
            .unwrap();
        harness.commit(refund, 900).unwrap();
        let finalize = harness
            .prepare(key(70), ModelInstruction::FinalizeClose, 901)
            .unwrap();
        harness.commit(finalize, 901).unwrap();
        assert_eq!(harness.snapshot().state.lifecycle, Lifecycle::Finalized);
        assert_eq!(harness.verify_serial_witness(), Ok(()));
    }

    proptest! {
        #![proptest_config(ProptestConfig {
            cases: 512,
            max_shrink_iters: 4096,
            .. ProptestConfig::default()
        })]

        #[test]
        fn concurrent_settlement_pairs_are_linearizable(
            first_amount in 1u64..=40,
            second_amount in 1u64..=40,
            first_wins in any::<bool>(),
            first_id in any::<[u8; 32]>(),
            second_id in any::<[u8; 32]>(),
        ) {
            prop_assume!(first_id != second_id);
            let state = active(100, 40, 0);
            let mut harness = LinearizationHarness::new(state).unwrap();
            let first = harness.prepare(
                first_id,
                settlement(&harness.snapshot().state, 1, first_amount),
                1,
            ).unwrap();
            let second = harness.prepare(
                second_id,
                settlement(&harness.snapshot().state, 2, second_amount),
                1,
            ).unwrap();
            let (winner, loser) = if first_wins {
                (first, second)
            } else {
                (second, first)
            };
            harness.commit(winner, 1).unwrap();
            prop_assert_eq!(
                harness.commit(loser, 1),
                Err(ConcurrencyError::StaleSnapshot)
            );
            prop_assert!(harness.snapshot().state.settled <= 40);
            prop_assert!(vault_conservation_holds(&harness.snapshot().state));
            prop_assert_eq!(harness.verify_serial_witness(), Ok(()));
        }
    }
}
