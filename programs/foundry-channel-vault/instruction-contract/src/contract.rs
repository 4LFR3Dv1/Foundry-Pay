//! Closed account, authority, event, and error registries.

use crate::instruction::InstructionKind;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum AuthorityKind {
    SenderTransactionSigner,
    SenderVoucherEd25519,
    ClaimAndDestinationEd25519,
    BoundRecipientState,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct AccountRequirement {
    pub name: &'static str,
    pub signer: bool,
    pub writable: bool,
    pub owner_rule: &'static str,
    pub address_rule: &'static str,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InstructionContract {
    pub kind: InstructionKind,
    pub authority: AuthorityKind,
    pub allowed_phases: &'static [&'static str],
    pub accounts: &'static [AccountRequirement],
    pub success_event: ChannelEventCode,
}

pub type AccountContract = InstructionContract;

const CHANNEL_RW: AccountRequirement = AccountRequirement {
    name: "channel",
    signer: false,
    writable: true,
    owner_rule: "foundry_channel_vault_program",
    address_rule: "pda(channel,sender,mint,channel_nonce)",
};
const SENDER_SIGNER: AccountRequirement = AccountRequirement {
    name: "sender",
    signer: true,
    writable: false,
    owner_rule: "system_account_or_wallet",
    address_rule: "equals_channel_sender_when_channel_exists",
};
const VAULT_RW: AccountRequirement = AccountRequirement {
    name: "vault",
    signer: false,
    writable: true,
    owner_rule: "classic_spl_token_program",
    address_rule: "canonical_vault_for_channel_pda_and_mint",
};
const MINT_RO: AccountRequirement = AccountRequirement {
    name: "mint",
    signer: false,
    writable: false,
    owner_rule: "classic_spl_token_program",
    address_rule: "equals_channel_mint",
};
const TOKEN_PROGRAM: AccountRequirement = AccountRequirement {
    name: "token_program",
    signer: false,
    writable: false,
    owner_rule: "executable",
    address_rule: "classic_spl_token_program_id",
};
const INSTRUCTIONS_SYSVAR: AccountRequirement = AccountRequirement {
    name: "instructions_sysvar",
    signer: false,
    writable: false,
    owner_rule: "sysvar",
    address_rule: "solana_instructions_sysvar_id",
};
const RECIPIENT_TOKEN_RW: AccountRequirement = AccountRequirement {
    name: "recipient_token_account",
    signer: false,
    writable: true,
    owner_rule: "classic_spl_token_program",
    address_rule: "canonical_ata(bound_recipient_wallet,channel_mint)",
};
const SENDER_TOKEN_RW: AccountRequirement = AccountRequirement {
    name: "sender_token_account",
    signer: false,
    writable: true,
    owner_rule: "classic_spl_token_program",
    address_rule: "canonical_ata(channel_sender,channel_mint)",
};

const INITIALIZE: &[AccountRequirement] = &[CHANNEL_RW, SENDER_SIGNER, MINT_RO, VAULT_RW];
const FUND: &[AccountRequirement] = &[
    CHANNEL_RW,
    SENDER_SIGNER,
    SENDER_TOKEN_RW,
    VAULT_RW,
    MINT_RO,
    TOKEN_PROGRAM,
];
const ACTIVATE: &[AccountRequirement] = &[CHANNEL_RW, INSTRUCTIONS_SYSVAR];
const BIND: &[AccountRequirement] = &[CHANNEL_RW, INSTRUCTIONS_SYSVAR];
const SETTLE: &[AccountRequirement] = &[
    CHANNEL_RW,
    VAULT_RW,
    RECIPIENT_TOKEN_RW,
    MINT_RO,
    TOKEN_PROGRAM,
];
const REQUEST_CLOSE: &[AccountRequirement] = &[CHANNEL_RW, SENDER_SIGNER];
const REFUND: &[AccountRequirement] = &[
    CHANNEL_RW,
    SENDER_SIGNER,
    VAULT_RW,
    SENDER_TOKEN_RW,
    MINT_RO,
    TOKEN_PROGRAM,
];
const FINALIZE: &[AccountRequirement] = &[CHANNEL_RW, SENDER_SIGNER, VAULT_RW];

pub const ACCOUNT_CONTRACTS: [InstructionContract; 8] = [
    InstructionContract {
        kind: InstructionKind::InitializeChannel,
        authority: AuthorityKind::SenderTransactionSigner,
        allowed_phases: &["uninitialized"],
        accounts: INITIALIZE,
        success_event: ChannelEventCode::ChannelInitialized,
    },
    InstructionContract {
        kind: InstructionKind::FundChannel,
        authority: AuthorityKind::SenderTransactionSigner,
        allowed_phases: &["active"],
        accounts: FUND,
        success_event: ChannelEventCode::ChannelFunded,
    },
    InstructionContract {
        kind: InstructionKind::ActivateVoucher,
        authority: AuthorityKind::SenderVoucherEd25519,
        allowed_phases: &["active", "closing_open"],
        accounts: ACTIVATE,
        success_event: ChannelEventCode::VoucherActivated,
    },
    InstructionContract {
        kind: InstructionKind::BindRecipient,
        authority: AuthorityKind::ClaimAndDestinationEd25519,
        allowed_phases: &["active", "closing_open"],
        accounts: BIND,
        success_event: ChannelEventCode::RecipientBound,
    },
    InstructionContract {
        kind: InstructionKind::Settle,
        authority: AuthorityKind::BoundRecipientState,
        allowed_phases: &["active", "closing_open", "closing_frozen"],
        accounts: SETTLE,
        success_event: ChannelEventCode::SettlementExecuted,
    },
    InstructionContract {
        kind: InstructionKind::RequestClose,
        authority: AuthorityKind::SenderTransactionSigner,
        allowed_phases: &["active"],
        accounts: REQUEST_CLOSE,
        success_event: ChannelEventCode::CloseRequested,
    },
    InstructionContract {
        kind: InstructionKind::RefundUnallocated,
        authority: AuthorityKind::SenderTransactionSigner,
        allowed_phases: &["closing_frozen"],
        accounts: REFUND,
        success_event: ChannelEventCode::RefundExecuted,
    },
    InstructionContract {
        kind: InstructionKind::FinalizeClose,
        authority: AuthorityKind::SenderTransactionSigner,
        allowed_phases: &["closing_frozen"],
        accounts: FINALIZE,
        success_event: ChannelEventCode::ChannelFinalized,
    },
];

pub fn account_contract(kind: InstructionKind) -> &'static InstructionContract {
    &ACCOUNT_CONTRACTS[kind as usize]
}

#[repr(u16)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ChannelEventCode {
    ChannelInitialized = 1,
    ChannelFunded = 2,
    VoucherActivated = 3,
    RecipientBound = 4,
    SettlementExecuted = 5,
    CloseRequested = 6,
    RefundExecuted = 7,
    ChannelFinalized = 8,
}

pub const EVENT_CONTRACTS: [(&str, ChannelEventCode); 8] = [
    ("ChannelInitialized", ChannelEventCode::ChannelInitialized),
    ("ChannelFunded", ChannelEventCode::ChannelFunded),
    ("VoucherActivated", ChannelEventCode::VoucherActivated),
    ("RecipientBound", ChannelEventCode::RecipientBound),
    ("SettlementExecuted", ChannelEventCode::SettlementExecuted),
    ("CloseRequested", ChannelEventCode::CloseRequested),
    ("RefundExecuted", ChannelEventCode::RefundExecuted),
    ("ChannelFinalized", ChannelEventCode::ChannelFinalized),
];

pub fn event_contract(code: ChannelEventCode) -> &'static str {
    EVENT_CONTRACTS
        .iter()
        .find(|(_, candidate)| *candidate == code)
        .map(|(name, _)| *name)
        .expect("closed event code")
}

#[repr(u32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ContractErrorCode {
    InvalidInstructionLength = 1000,
    UnknownInstruction = 1001,
    UnsupportedInstructionVersion = 1002,
    UnsupportedProfile = 1003,
    MissingSigner = 2000,
    WrongAccountOwner = 2001,
    WrongPda = 2002,
    WrongAccountAddress = 2003,
    WrongMint = 3000,
    WrongVault = 3001,
    WrongVaultAuthority = 3002,
    UnsupportedTokenProgram = 3003,
    LifecycleViolation = 4000,
    ExpiredAuthority = 4001,
    FinalizedChannel = 4002,
    WrongEd25519Program = 5000,
    Ed25519NotImmediatelyPreceding = 5001,
    NonCanonicalEd25519Header = 5002,
    ExternalEd25519Reference = 5003,
    NonCanonicalEd25519Offsets = 5004,
    WrongEd25519PublicKey = 5005,
    WrongEd25519Message = 5006,
    SequenceReplay = 6000,
    SequenceRegression = 6001,
    BindingNonceConsumed = 6002,
    RecipientSubstitution = 6003,
    ConservationViolation = 7000,
    InsufficientUnallocatedCapacity = 7001,
    InsufficientActivatedRight = 7002,
    CheckedArithmeticFailure = 7003,
}

pub const ERROR_REGISTRY: &[(&str, ContractErrorCode)] = &[
    (
        "INVALID_INSTRUCTION_LENGTH",
        ContractErrorCode::InvalidInstructionLength,
    ),
    ("UNKNOWN_INSTRUCTION", ContractErrorCode::UnknownInstruction),
    (
        "UNSUPPORTED_INSTRUCTION_VERSION",
        ContractErrorCode::UnsupportedInstructionVersion,
    ),
    ("UNSUPPORTED_PROFILE", ContractErrorCode::UnsupportedProfile),
    ("MISSING_SIGNER", ContractErrorCode::MissingSigner),
    ("WRONG_ACCOUNT_OWNER", ContractErrorCode::WrongAccountOwner),
    ("WRONG_PDA", ContractErrorCode::WrongPda),
    (
        "WRONG_ACCOUNT_ADDRESS",
        ContractErrorCode::WrongAccountAddress,
    ),
    ("WRONG_MINT", ContractErrorCode::WrongMint),
    ("WRONG_VAULT", ContractErrorCode::WrongVault),
    (
        "WRONG_VAULT_AUTHORITY",
        ContractErrorCode::WrongVaultAuthority,
    ),
    (
        "UNSUPPORTED_TOKEN_PROGRAM",
        ContractErrorCode::UnsupportedTokenProgram,
    ),
    ("LIFECYCLE_VIOLATION", ContractErrorCode::LifecycleViolation),
    ("EXPIRED_AUTHORITY", ContractErrorCode::ExpiredAuthority),
    ("FINALIZED_CHANNEL", ContractErrorCode::FinalizedChannel),
    (
        "WRONG_ED25519_PROGRAM",
        ContractErrorCode::WrongEd25519Program,
    ),
    (
        "ED25519_NOT_IMMEDIATELY_PRECEDING",
        ContractErrorCode::Ed25519NotImmediatelyPreceding,
    ),
    (
        "NON_CANONICAL_ED25519_HEADER",
        ContractErrorCode::NonCanonicalEd25519Header,
    ),
    (
        "EXTERNAL_ED25519_REFERENCE",
        ContractErrorCode::ExternalEd25519Reference,
    ),
    (
        "NON_CANONICAL_ED25519_OFFSETS",
        ContractErrorCode::NonCanonicalEd25519Offsets,
    ),
    (
        "WRONG_ED25519_PUBLIC_KEY",
        ContractErrorCode::WrongEd25519PublicKey,
    ),
    (
        "WRONG_ED25519_MESSAGE",
        ContractErrorCode::WrongEd25519Message,
    ),
    ("SEQUENCE_REPLAY", ContractErrorCode::SequenceReplay),
    ("SEQUENCE_REGRESSION", ContractErrorCode::SequenceRegression),
    (
        "BINDING_NONCE_CONSUMED",
        ContractErrorCode::BindingNonceConsumed,
    ),
    (
        "RECIPIENT_SUBSTITUTION",
        ContractErrorCode::RecipientSubstitution,
    ),
    (
        "CONSERVATION_VIOLATION",
        ContractErrorCode::ConservationViolation,
    ),
    (
        "INSUFFICIENT_UNALLOCATED_CAPACITY",
        ContractErrorCode::InsufficientUnallocatedCapacity,
    ),
    (
        "INSUFFICIENT_ACTIVATED_RIGHT",
        ContractErrorCode::InsufficientActivatedRight,
    ),
    (
        "CHECKED_ARITHMETIC_FAILURE",
        ContractErrorCode::CheckedArithmeticFailure,
    ),
];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_instruction_has_one_closed_contract_and_fact_event() {
        assert_eq!(ACCOUNT_CONTRACTS.len(), 8);
        assert_eq!(EVENT_CONTRACTS.len(), 8);
        for kind in InstructionKind::ALL {
            let contract = account_contract(kind);
            assert_eq!(contract.kind, kind);
            assert!(!contract.accounts.is_empty());
            assert!(!event_contract(contract.success_event).contains("Payment"));
            assert!(!event_contract(contract.success_event).contains("Business"));
        }
    }

    #[test]
    fn error_codes_are_unique() {
        let mut codes: Vec<_> = ERROR_REGISTRY
            .iter()
            .map(|(_, code)| *code as u32)
            .collect();
        let original_len = codes.len();
        codes.sort_unstable();
        codes.dedup();
        assert_eq!(codes.len(), original_len);
    }
}
