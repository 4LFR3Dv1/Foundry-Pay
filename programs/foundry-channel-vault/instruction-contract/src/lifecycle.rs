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
}
