//! Lifecycle phases derived without changing the FC-SOL-002 account layout.

use foundry_channel_vault_account_model::StatusCode;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LifecyclePhase {
    Active,
    ClosingOpen,
    ClosingFrozen,
    Finalized,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LifecycleContractError {
    UnsupportedPersistentStatus(StatusCode),
    ClosingDeadlineMissing,
    ClaimDeadlineTooSoon,
    ClaimDeadlineTooLate,
    CheckedArithmeticFailure,
}

pub const MIN_CLAIM_WINDOW_SECONDS: i64 = 900;
pub const MAX_CLAIM_WINDOW_SECONDS: i64 = 2_592_000;

pub fn validate_claim_deadline(
    now: i64,
    claim_deadline: i64,
) -> Result<(), LifecycleContractError> {
    let minimum = now
        .checked_add(MIN_CLAIM_WINDOW_SECONDS)
        .ok_or(LifecycleContractError::CheckedArithmeticFailure)?;
    let maximum = now
        .checked_add(MAX_CLAIM_WINDOW_SECONDS)
        .ok_or(LifecycleContractError::CheckedArithmeticFailure)?;
    if claim_deadline < minimum {
        return Err(LifecycleContractError::ClaimDeadlineTooSoon);
    }
    if claim_deadline > maximum {
        return Err(LifecycleContractError::ClaimDeadlineTooLate);
    }
    Ok(())
}

pub fn derive_lifecycle_phase(
    status: StatusCode,
    claim_deadline: Option<i64>,
    now: i64,
) -> Result<LifecyclePhase, LifecycleContractError> {
    match status {
        StatusCode::Active => Ok(LifecyclePhase::Active),
        StatusCode::Closing => {
            let deadline = claim_deadline.ok_or(LifecycleContractError::ClosingDeadlineMissing)?;
            if now < deadline {
                Ok(LifecyclePhase::ClosingOpen)
            } else {
                Ok(LifecyclePhase::ClosingFrozen)
            }
        }
        StatusCode::Closed => Ok(LifecyclePhase::Finalized),
        other => Err(LifecycleContractError::UnsupportedPersistentStatus(other)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deadline_is_exclusive_for_activation() {
        assert_eq!(
            derive_lifecycle_phase(StatusCode::Closing, Some(100), 99),
            Ok(LifecyclePhase::ClosingOpen)
        );
        assert_eq!(
            derive_lifecycle_phase(StatusCode::Closing, Some(100), 100),
            Ok(LifecyclePhase::ClosingFrozen)
        );
    }

    #[test]
    fn finalized_is_explicit_and_terminal() {
        assert_eq!(
            derive_lifecycle_phase(StatusCode::Closed, None, 0),
            Ok(LifecyclePhase::Finalized)
        );
        assert_eq!(
            derive_lifecycle_phase(StatusCode::Settling, None, 0),
            Err(LifecycleContractError::UnsupportedPersistentStatus(
                StatusCode::Settling
            ))
        );
    }

    #[test]
    fn claim_window_accepts_exact_bounds_and_rejects_outside() {
        let now = 1_700_000_000;
        assert_eq!(
            validate_claim_deadline(now, now + MIN_CLAIM_WINDOW_SECONDS),
            Ok(())
        );
        assert_eq!(
            validate_claim_deadline(now, now + MAX_CLAIM_WINDOW_SECONDS),
            Ok(())
        );
        assert_eq!(
            validate_claim_deadline(now, now + MIN_CLAIM_WINDOW_SECONDS - 1),
            Err(LifecycleContractError::ClaimDeadlineTooSoon)
        );
        assert_eq!(
            validate_claim_deadline(now, now + MAX_CLAIM_WINDOW_SECONDS + 1),
            Err(LifecycleContractError::ClaimDeadlineTooLate)
        );
    }

    #[test]
    fn claim_window_uses_checked_time_arithmetic() {
        assert_eq!(
            validate_claim_deadline(i64::MAX, i64::MAX),
            Err(LifecycleContractError::CheckedArithmeticFailure)
        );
    }
}
