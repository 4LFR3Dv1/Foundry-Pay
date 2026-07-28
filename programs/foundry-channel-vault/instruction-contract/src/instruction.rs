//! Fixed-width experimental ChannelVault instruction serialization.

use sha2::{Digest, Sha256};
use solana_pubkey::Pubkey;
use std::fmt;

pub const INSTRUCTION_CONTRACT_VERSION_V1: u16 = 1;

#[repr(u8)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum InstructionKind {
    InitializeChannel = 0,
    FundChannel = 1,
    ActivateVoucher = 2,
    BindRecipient = 3,
    Settle = 4,
    RequestClose = 5,
    RefundUnallocated = 6,
    FinalizeClose = 7,
}

impl InstructionKind {
    pub const ALL: [Self; 8] = [
        Self::InitializeChannel,
        Self::FundChannel,
        Self::ActivateVoucher,
        Self::BindRecipient,
        Self::Settle,
        Self::RequestClose,
        Self::RefundUnallocated,
        Self::FinalizeClose,
    ];

    pub const fn name(self) -> &'static str {
        match self {
            Self::InitializeChannel => "initialize_channel",
            Self::FundChannel => "fund_channel",
            Self::ActivateVoucher => "activate_voucher",
            Self::BindRecipient => "bind_recipient",
            Self::Settle => "settle",
            Self::RequestClose => "request_close",
            Self::RefundUnallocated => "refund_unallocated",
            Self::FinalizeClose => "finalize_close",
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ChannelInstruction {
    InitializeChannel {
        channel_nonce: [u8; 32],
        recipient_claim_pubkey: Pubkey,
        decimals: u8,
        channel_expiry: i64,
    },
    FundChannel {
        amount: u64,
    },
    ActivateVoucher {
        sequence: u64,
        cumulative_authorized: u64,
        voucher_hash: [u8; 32],
        voucher_expiry: i64,
    },
    BindRecipient {
        binding_nonce: [u8; 32],
        destination_wallet: Pubkey,
        binding_hash: [u8; 32],
    },
    Settle {
        amount: u64,
        obligation_hash: [u8; 32],
    },
    RequestClose {
        claim_deadline: i64,
    },
    RefundUnallocated {
        amount: u64,
        refund_request_hash: [u8; 32],
    },
    FinalizeClose {
        finalization_hash: [u8; 32],
    },
}

impl ChannelInstruction {
    pub fn kind(&self) -> InstructionKind {
        match self {
            Self::InitializeChannel { .. } => InstructionKind::InitializeChannel,
            Self::FundChannel { .. } => InstructionKind::FundChannel,
            Self::ActivateVoucher { .. } => InstructionKind::ActivateVoucher,
            Self::BindRecipient { .. } => InstructionKind::BindRecipient,
            Self::Settle { .. } => InstructionKind::Settle,
            Self::RequestClose { .. } => InstructionKind::RequestClose,
            Self::RefundUnallocated { .. } => InstructionKind::RefundUnallocated,
            Self::FinalizeClose { .. } => InstructionKind::FinalizeClose,
        }
    }

    pub fn encode(&self) -> Vec<u8> {
        let kind = self.kind();
        let mut output = Vec::with_capacity(self.encoded_len());
        output.extend_from_slice(&instruction_discriminator(kind));
        output.extend_from_slice(&INSTRUCTION_CONTRACT_VERSION_V1.to_le_bytes());
        match self {
            Self::InitializeChannel {
                channel_nonce,
                recipient_claim_pubkey,
                decimals,
                channel_expiry,
            } => {
                output.extend_from_slice(channel_nonce);
                output.extend_from_slice(recipient_claim_pubkey.as_ref());
                output.push(*decimals);
                output.extend_from_slice(&channel_expiry.to_le_bytes());
            }
            Self::FundChannel { amount } => output.extend_from_slice(&amount.to_le_bytes()),
            Self::ActivateVoucher {
                sequence,
                cumulative_authorized,
                voucher_hash,
                voucher_expiry,
            } => {
                output.extend_from_slice(&sequence.to_le_bytes());
                output.extend_from_slice(&cumulative_authorized.to_le_bytes());
                output.extend_from_slice(voucher_hash);
                output.extend_from_slice(&voucher_expiry.to_le_bytes());
            }
            Self::BindRecipient {
                binding_nonce,
                destination_wallet,
                binding_hash,
            } => {
                output.extend_from_slice(binding_nonce);
                output.extend_from_slice(destination_wallet.as_ref());
                output.extend_from_slice(binding_hash);
            }
            Self::Settle {
                amount,
                obligation_hash,
            } => {
                output.extend_from_slice(&amount.to_le_bytes());
                output.extend_from_slice(obligation_hash);
            }
            Self::RequestClose { claim_deadline } => {
                output.extend_from_slice(&claim_deadline.to_le_bytes());
            }
            Self::RefundUnallocated {
                amount,
                refund_request_hash,
            } => {
                output.extend_from_slice(&amount.to_le_bytes());
                output.extend_from_slice(refund_request_hash);
            }
            Self::FinalizeClose { finalization_hash } => {
                output.extend_from_slice(finalization_hash);
            }
        }
        output
    }

    pub fn decode(input: &[u8]) -> Result<Self, InstructionDecodeError> {
        if input.len() < 10 {
            return Err(InstructionDecodeError::WrongLength);
        }
        let discriminator: [u8; 8] = input[..8]
            .try_into()
            .map_err(|_| InstructionDecodeError::WrongLength)?;
        let version = u16::from_le_bytes([input[8], input[9]]);
        if version != INSTRUCTION_CONTRACT_VERSION_V1 {
            return Err(InstructionDecodeError::UnsupportedVersion(version));
        }
        let kind = InstructionKind::ALL
            .into_iter()
            .find(|candidate| instruction_discriminator(*candidate) == discriminator)
            .ok_or(InstructionDecodeError::UnknownDiscriminator)?;
        let payload = &input[10..];
        decode_payload(kind, payload)
    }

    fn encoded_len(&self) -> usize {
        10 + match self {
            Self::InitializeChannel { .. } => 32 + 32 + 1 + 8,
            Self::FundChannel { .. } => 8,
            Self::ActivateVoucher { .. } => 8 + 8 + 32 + 8,
            Self::BindRecipient { .. } => 32 + 32 + 32,
            Self::Settle { .. } => 8 + 32,
            Self::RequestClose { .. } => 8,
            Self::RefundUnallocated { .. } => 8 + 32,
            Self::FinalizeClose { .. } => 32,
        }
    }
}

pub fn instruction_discriminator(kind: InstructionKind) -> [u8; 8] {
    let digest = Sha256::digest(format!("global:{}", kind.name()).as_bytes());
    digest[..8]
        .try_into()
        .expect("SHA-256 digest always has at least eight bytes")
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum InstructionDecodeError {
    WrongLength,
    UnknownDiscriminator,
    UnsupportedVersion(u16),
}

impl fmt::Display for InstructionDecodeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{self:?}")
    }
}

impl std::error::Error for InstructionDecodeError {}

fn decode_payload(
    kind: InstructionKind,
    payload: &[u8],
) -> Result<ChannelInstruction, InstructionDecodeError> {
    let exact = |length: usize| {
        if payload.len() == length {
            Ok(())
        } else {
            Err(InstructionDecodeError::WrongLength)
        }
    };
    match kind {
        InstructionKind::InitializeChannel => {
            exact(73)?;
            Ok(ChannelInstruction::InitializeChannel {
                channel_nonce: payload[0..32].try_into().unwrap(),
                recipient_claim_pubkey: Pubkey::new_from_array(payload[32..64].try_into().unwrap()),
                decimals: payload[64],
                channel_expiry: i64::from_le_bytes(payload[65..73].try_into().unwrap()),
            })
        }
        InstructionKind::FundChannel => {
            exact(8)?;
            Ok(ChannelInstruction::FundChannel {
                amount: u64::from_le_bytes(payload.try_into().unwrap()),
            })
        }
        InstructionKind::ActivateVoucher => {
            exact(56)?;
            Ok(ChannelInstruction::ActivateVoucher {
                sequence: u64::from_le_bytes(payload[0..8].try_into().unwrap()),
                cumulative_authorized: u64::from_le_bytes(payload[8..16].try_into().unwrap()),
                voucher_hash: payload[16..48].try_into().unwrap(),
                voucher_expiry: i64::from_le_bytes(payload[48..56].try_into().unwrap()),
            })
        }
        InstructionKind::BindRecipient => {
            exact(96)?;
            Ok(ChannelInstruction::BindRecipient {
                binding_nonce: payload[0..32].try_into().unwrap(),
                destination_wallet: Pubkey::new_from_array(payload[32..64].try_into().unwrap()),
                binding_hash: payload[64..96].try_into().unwrap(),
            })
        }
        InstructionKind::Settle => {
            exact(40)?;
            Ok(ChannelInstruction::Settle {
                amount: u64::from_le_bytes(payload[0..8].try_into().unwrap()),
                obligation_hash: payload[8..40].try_into().unwrap(),
            })
        }
        InstructionKind::RequestClose => {
            exact(8)?;
            Ok(ChannelInstruction::RequestClose {
                claim_deadline: i64::from_le_bytes(payload.try_into().unwrap()),
            })
        }
        InstructionKind::RefundUnallocated => {
            exact(40)?;
            Ok(ChannelInstruction::RefundUnallocated {
                amount: u64::from_le_bytes(payload[0..8].try_into().unwrap()),
                refund_request_hash: payload[8..40].try_into().unwrap(),
            })
        }
        InstructionKind::FinalizeClose => {
            exact(32)?;
            Ok(ChannelInstruction::FinalizeClose {
                finalization_hash: payload.try_into().unwrap(),
            })
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixtures() -> Vec<ChannelInstruction> {
        vec![
            ChannelInstruction::InitializeChannel {
                channel_nonce: [1; 32],
                recipient_claim_pubkey: Pubkey::new_from_array([2; 32]),
                decimals: 6,
                channel_expiry: 1_800_000_000,
            },
            ChannelInstruction::FundChannel { amount: 100 },
            ChannelInstruction::ActivateVoucher {
                sequence: 3,
                cumulative_authorized: 40,
                voucher_hash: [3; 32],
                voucher_expiry: 1_750_000_000,
            },
            ChannelInstruction::BindRecipient {
                binding_nonce: [4; 32],
                destination_wallet: Pubkey::new_from_array([5; 32]),
                binding_hash: [6; 32],
            },
            ChannelInstruction::Settle {
                amount: 25,
                obligation_hash: [7; 32],
            },
            ChannelInstruction::RequestClose {
                claim_deadline: 1_700_086_400,
            },
            ChannelInstruction::RefundUnallocated {
                amount: 60,
                refund_request_hash: [8; 32],
            },
            ChannelInstruction::FinalizeClose {
                finalization_hash: [9; 32],
            },
        ]
    }

    #[test]
    fn all_instructions_round_trip_exactly() {
        for instruction in fixtures() {
            let encoded = instruction.encode();
            assert_eq!(ChannelInstruction::decode(&encoded), Ok(instruction));
        }
    }

    #[test]
    fn rejects_unknown_version_discriminator_and_trailing_bytes() {
        let encoded = ChannelInstruction::FundChannel { amount: 1 }.encode();

        let mut version = encoded.clone();
        version[8..10].copy_from_slice(&2_u16.to_le_bytes());
        assert_eq!(
            ChannelInstruction::decode(&version),
            Err(InstructionDecodeError::UnsupportedVersion(2))
        );

        let mut discriminator = encoded.clone();
        discriminator[0] ^= 1;
        assert_eq!(
            ChannelInstruction::decode(&discriminator),
            Err(InstructionDecodeError::UnknownDiscriminator)
        );

        let mut trailing = encoded;
        trailing.push(0);
        assert_eq!(
            ChannelInstruction::decode(&trailing),
            Err(InstructionDecodeError::WrongLength)
        );
    }
}
