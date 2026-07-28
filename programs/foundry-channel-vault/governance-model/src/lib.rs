//! Offline governance and migration model for Foundry Channels.
//!
//! This crate does not interact with the Solana loader, accounts, multisigs,
//! token programs, RPC, or deployment environments.

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use thiserror::Error;

pub type Authority = [u8; 32];

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ChangeClass {
    Compatible,
    Versioned,
    Forbidden,
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct ChangeDescription {
    pub changes_normative_bytes: bool,
    pub changes_authority: bool,
    pub changes_lifecycle: bool,
    pub changes_temporal_bounds: bool,
    pub changes_account_meaning: bool,
    pub reinterprets_reserved_v1_bytes: bool,
    pub reduces_activated_right: bool,
    pub redirects_outstanding_right: bool,
    pub merges_outstanding_and_unallocated: bool,
    pub permits_unilateral_rebind: bool,
    pub refunds_reserved_capacity: bool,
    pub adds_third_party_settlement_control: bool,
}

pub fn classify_change(change: &ChangeDescription) -> ChangeClass {
    if change.reinterprets_reserved_v1_bytes
        || change.reduces_activated_right
        || change.redirects_outstanding_right
        || change.merges_outstanding_and_unallocated
        || change.permits_unilateral_rebind
        || change.refunds_reserved_capacity
        || change.adds_third_party_settlement_control
    {
        ChangeClass::Forbidden
    } else if change.changes_normative_bytes
        || change.changes_authority
        || change.changes_lifecycle
        || change.changes_temporal_bounds
        || change.changes_account_meaning
    {
        ChangeClass::Versioned
    } else {
        ChangeClass::Compatible
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AuthorityPolicy {
    pub members: Vec<Authority>,
    pub threshold: usize,
    pub min_timelock_seconds: i64,
    pub emergency_authority: Authority,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct UpgradeManifest {
    pub change_class: ChangeClass,
    pub current_program_id: Authority,
    pub proposed_program_id: Authority,
    pub current_protocol_version: u16,
    pub proposed_protocol_version: u16,
    pub current_binary_hash: [u8; 32],
    pub proposed_binary_hash: [u8; 32],
    pub source_commit: [u8; 20],
    pub toolchain: String,
    pub lockfile_hash: [u8; 32],
    pub current_account_layout_hash: [u8; 32],
    pub proposed_account_layout_hash: [u8; 32],
    pub current_instruction_registry_hash: [u8; 32],
    pub proposed_instruction_registry_hash: [u8; 32],
    pub current_signed_message_registry_hash: [u8; 32],
    pub proposed_signed_message_registry_hash: [u8; 32],
    pub approved_at: i64,
    pub earliest_execution_at: i64,
    pub approvals: Vec<Authority>,
}

#[derive(Clone, Debug, Error, Eq, PartialEq)]
pub enum GovernanceError {
    #[error("authority set is empty or contains duplicates")]
    InvalidAuthoritySet,
    #[error("threshold is outside the authority set")]
    InvalidThreshold,
    #[error("timelock must be positive")]
    InvalidTimelock,
    #[error("approval threshold was not met")]
    InsufficientApprovals,
    #[error("an approval is not from a declared member")]
    UnknownApprover,
    #[error("timelock arithmetic overflowed")]
    TimelockOverflow,
    #[error("earliest execution violates the timelock")]
    TimelockViolation,
    #[error("forbidden change cannot be executed")]
    ForbiddenChange,
    #[error("compatible change altered a normative registry or Program ID")]
    IncompatibleSameProgramUpgrade,
    #[error("versioned change requires a new protocol version and Program ID")]
    VersionedChangeWithoutIsolation,
    #[error("artifact provenance is incomplete")]
    IncompleteArtifactBinding,
    #[error("migration changed an economic right or binding")]
    RightsNotPreserved,
}

pub fn validate_policy(policy: &AuthorityPolicy) -> Result<(), GovernanceError> {
    let unique: BTreeSet<_> = policy.members.iter().copied().collect();
    if policy.members.is_empty() || unique.len() != policy.members.len() {
        return Err(GovernanceError::InvalidAuthoritySet);
    }
    if policy.threshold < 2 || policy.threshold > policy.members.len() {
        return Err(GovernanceError::InvalidThreshold);
    }
    if policy.min_timelock_seconds <= 0 {
        return Err(GovernanceError::InvalidTimelock);
    }
    Ok(())
}

pub fn validate_manifest(
    policy: &AuthorityPolicy,
    manifest: &UpgradeManifest,
) -> Result<(), GovernanceError> {
    validate_policy(policy)?;
    if manifest.toolchain.trim().is_empty()
        || manifest.current_binary_hash == [0; 32]
        || manifest.proposed_binary_hash == [0; 32]
        || manifest.source_commit == [0; 20]
        || manifest.lockfile_hash == [0; 32]
    {
        return Err(GovernanceError::IncompleteArtifactBinding);
    }

    let approvals: BTreeSet<_> = manifest.approvals.iter().copied().collect();
    if approvals
        .iter()
        .any(|authority| !policy.members.contains(authority))
    {
        return Err(GovernanceError::UnknownApprover);
    }
    if approvals.len() < policy.threshold {
        return Err(GovernanceError::InsufficientApprovals);
    }

    let minimum = manifest
        .approved_at
        .checked_add(policy.min_timelock_seconds)
        .ok_or(GovernanceError::TimelockOverflow)?;
    if manifest.earliest_execution_at < minimum {
        return Err(GovernanceError::TimelockViolation);
    }

    match manifest.change_class {
        ChangeClass::Forbidden => Err(GovernanceError::ForbiddenChange),
        ChangeClass::Compatible => {
            let unchanged = manifest.current_program_id == manifest.proposed_program_id
                && manifest.current_protocol_version == manifest.proposed_protocol_version
                && manifest.current_account_layout_hash == manifest.proposed_account_layout_hash
                && manifest.current_instruction_registry_hash
                    == manifest.proposed_instruction_registry_hash
                && manifest.current_signed_message_registry_hash
                    == manifest.proposed_signed_message_registry_hash;
            if unchanged {
                Ok(())
            } else {
                Err(GovernanceError::IncompatibleSameProgramUpgrade)
            }
        }
        ChangeClass::Versioned => {
            if manifest.current_program_id != manifest.proposed_program_id
                && manifest.current_protocol_version != manifest.proposed_protocol_version
            {
                Ok(())
            } else {
                Err(GovernanceError::VersionedChangeWithoutIsolation)
            }
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EmergencyOperation {
    Initialize,
    Fund,
    ActivateVoucher,
    SettleActivatedRight,
    RefundEligibleUnallocated,
    FinalizeResolvedChannel,
    RebindRecipient,
    GovernanceSweep,
}

pub fn allowed_while_paused(operation: EmergencyOperation) -> bool {
    matches!(
        operation,
        EmergencyOperation::SettleActivatedRight
            | EmergencyOperation::RefundEligibleUnallocated
            | EmergencyOperation::FinalizeResolvedChannel
    )
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct RightsSnapshot {
    pub funded: u64,
    pub activated: u64,
    pub settled: u64,
    pub refunded: u64,
    pub latest_sequence: u64,
    pub latest_voucher_hash: [u8; 32],
    pub recipient_claim_key: Authority,
    pub recipient_wallet: Authority,
    pub recipient_bound: bool,
    pub mint: Authority,
    pub epoch: u64,
}

impl RightsSnapshot {
    pub fn outstanding_right(&self) -> Option<u64> {
        self.activated.checked_sub(self.settled)
    }

    pub fn unallocated_capacity(&self) -> Option<u64> {
        self.funded
            .checked_sub(self.refunded)?
            .checked_sub(self.activated)
    }
}

pub fn validate_migration(
    before: &RightsSnapshot,
    after: &RightsSnapshot,
) -> Result<(), GovernanceError> {
    if before != after
        || before.outstanding_right() != after.outstanding_right()
        || before.unallocated_capacity() != after.unallocated_capacity()
    {
        Err(GovernanceError::RightsNotPreserved)
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn key(value: u8) -> Authority {
        [value; 32]
    }

    fn policy() -> AuthorityPolicy {
        AuthorityPolicy {
            members: vec![key(1), key(2), key(3)],
            threshold: 2,
            min_timelock_seconds: 86_400,
            emergency_authority: key(9),
        }
    }

    fn manifest(class: ChangeClass) -> UpgradeManifest {
        UpgradeManifest {
            change_class: class,
            current_program_id: key(10),
            proposed_program_id: key(10),
            current_protocol_version: 1,
            proposed_protocol_version: 1,
            current_binary_hash: key(11),
            proposed_binary_hash: key(12),
            source_commit: [13; 20],
            toolchain: "rustc 1.85.1".into(),
            lockfile_hash: key(14),
            current_account_layout_hash: key(15),
            proposed_account_layout_hash: key(15),
            current_instruction_registry_hash: key(16),
            proposed_instruction_registry_hash: key(16),
            current_signed_message_registry_hash: key(17),
            proposed_signed_message_registry_hash: key(17),
            approved_at: 1_000_000,
            earliest_execution_at: 1_086_400,
            approvals: vec![key(1), key(2)],
        }
    }

    fn rights() -> RightsSnapshot {
        RightsSnapshot {
            funded: 100,
            activated: 40,
            settled: 15,
            refunded: 0,
            latest_sequence: 3,
            latest_voucher_hash: key(20),
            recipient_claim_key: key(21),
            recipient_wallet: key(22),
            recipient_bound: true,
            mint: key(23),
            epoch: 1,
        }
    }

    #[test]
    fn compatible_upgrade_requires_unchanged_normative_registries() {
        assert_eq!(
            validate_manifest(&policy(), &manifest(ChangeClass::Compatible)),
            Ok(())
        );
        let mut changed = manifest(ChangeClass::Compatible);
        changed.proposed_instruction_registry_hash = key(99);
        assert_eq!(
            validate_manifest(&policy(), &changed),
            Err(GovernanceError::IncompatibleSameProgramUpgrade)
        );
    }

    #[test]
    fn versioned_change_requires_new_version_and_program_id() {
        let mut changed = manifest(ChangeClass::Versioned);
        assert_eq!(
            validate_manifest(&policy(), &changed),
            Err(GovernanceError::VersionedChangeWithoutIsolation)
        );
        changed.proposed_protocol_version = 2;
        changed.proposed_program_id = key(42);
        assert_eq!(validate_manifest(&policy(), &changed), Ok(()));
    }

    #[test]
    fn forbidden_rights_change_never_executes() {
        let change = ChangeDescription {
            reduces_activated_right: true,
            ..Default::default()
        };
        assert_eq!(classify_change(&change), ChangeClass::Forbidden);
        assert_eq!(
            validate_manifest(&policy(), &manifest(ChangeClass::Forbidden)),
            Err(GovernanceError::ForbiddenChange)
        );
    }

    #[test]
    fn threshold_and_timelock_are_fail_closed() {
        let mut insufficient = manifest(ChangeClass::Compatible);
        insufficient.approvals = vec![key(1)];
        assert_eq!(
            validate_manifest(&policy(), &insufficient),
            Err(GovernanceError::InsufficientApprovals)
        );
        let mut early = manifest(ChangeClass::Compatible);
        early.earliest_execution_at -= 1;
        assert_eq!(
            validate_manifest(&policy(), &early),
            Err(GovernanceError::TimelockViolation)
        );
    }

    #[test]
    fn emergency_pause_blocks_ingress_and_preserves_exits() {
        assert!(!allowed_while_paused(EmergencyOperation::Initialize));
        assert!(!allowed_while_paused(EmergencyOperation::Fund));
        assert!(!allowed_while_paused(EmergencyOperation::ActivateVoucher));
        assert!(allowed_while_paused(
            EmergencyOperation::SettleActivatedRight
        ));
        assert!(allowed_while_paused(
            EmergencyOperation::RefundEligibleUnallocated
        ));
        assert!(allowed_while_paused(
            EmergencyOperation::FinalizeResolvedChannel
        ));
        assert!(!allowed_while_paused(EmergencyOperation::GovernanceSweep));
    }

    #[test]
    fn migration_preserves_distinct_rights_buckets_and_binding() {
        let before = rights();
        assert_eq!(before.outstanding_right(), Some(25));
        assert_eq!(before.unallocated_capacity(), Some(60));
        assert_eq!(validate_migration(&before, &before.clone()), Ok(()));

        let mut redirected = before.clone();
        redirected.recipient_wallet = key(99);
        assert_eq!(
            validate_migration(&before, &redirected),
            Err(GovernanceError::RightsNotPreserved)
        );
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(512))]

        #[test]
        fn any_economic_or_binding_mutation_is_rejected(
            settled in 0u64..100_000,
            outstanding in 0u64..100_000,
            unallocated in 0u64..100_000,
            refunded in 0u64..100_000,
            selector in 0u8..6,
        ) {
            let activated = settled + outstanding;
            let funded = activated + unallocated + refunded;
            let before = RightsSnapshot {
                funded,
                activated,
                settled,
                refunded,
                latest_sequence: 4,
                latest_voucher_hash: key(31),
                recipient_claim_key: key(32),
                recipient_wallet: key(33),
                recipient_bound: true,
                mint: key(34),
                epoch: 1,
            };
            let mut after = before.clone();
            match selector {
                0 => after.funded = after.funded.saturating_add(1),
                1 => after.activated = after.activated.saturating_add(1),
                2 => after.settled = after.settled.saturating_add(1),
                3 => after.refunded = after.refunded.saturating_add(1),
                4 => after.recipient_wallet = key(99),
                _ => after.latest_sequence = after.latest_sequence.saturating_add(1),
            }
            prop_assert_eq!(
                validate_migration(&before, &after),
                Err(GovernanceError::RightsNotPreserved)
            );
        }
    }
}
