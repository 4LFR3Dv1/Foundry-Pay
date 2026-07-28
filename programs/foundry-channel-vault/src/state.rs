use solana_pubkey::Pubkey;
use std::fmt;

pub const CHANNEL_STATE_DISCRIMINATOR: [u8; 8] = [74, 132, 141, 196, 64, 52, 83, 136];
pub const CHANNEL_STATE_VERSION_V1: u16 = 1;
pub const CHANNEL_STATE_RESERVED_BYTES: usize = 64;
pub const CHANNEL_STATE_SPACE: usize = 490;
pub const KNOWN_POLICY_FLAGS: u32 = 0b11;
pub const CHANNEL_STATE_FIELDS: &[(&str, usize, usize)] = &[
    ("discriminator", 0, 8),
    ("account_version", 8, 2),
    ("bump", 10, 1),
    ("status", 11, 1),
    ("environment", 12, 1),
    ("network", 13, 1),
    ("program_version", 14, 2),
    ("policy_flags", 16, 4),
    ("genesis_hash", 20, 32),
    ("channel_nonce", 52, 32),
    ("channel_id_hash", 84, 32),
    ("epoch", 116, 8),
    ("sender", 124, 32),
    ("recipient_claim_pubkey", 156, 32),
    ("recipient_wallet", 188, 32),
    ("recipient_bound", 220, 1),
    ("binding_nonce", 221, 32),
    ("mint", 253, 32),
    ("vault_token_account", 285, 32),
    ("decimals", 317, 1),
    ("funded_total", 318, 8),
    ("activated_authorized_total", 326, 8),
    ("settled_total", 334, 8),
    ("refunded_total", 342, 8),
    ("latest_activated_sequence", 350, 8),
    ("latest_activated_voucher_hash", 358, 32),
    ("channel_expiry_set", 390, 1),
    ("channel_expiry", 391, 8),
    ("voucher_expiry_set", 399, 1),
    ("voucher_expiry", 400, 8),
    ("close_requested", 408, 1),
    ("close_requested_at", 409, 8),
    ("claim_deadline_set", 417, 1),
    ("claim_deadline", 418, 8),
    ("reserved", 426, 64),
];

#[repr(u8)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum StatusCode {
    Draft = 0,
    Funding = 1,
    Active = 2,
    Settling = 3,
    Closing = 4,
    Closed = 5,
    Expired = 6,
    Blocked = 7,
    Disputed = 8,
    NeedsRecovery = 9,
    NeedsReview = 10,
}

impl TryFrom<u8> for StatusCode {
    type Error = ChannelStateError;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            0 => Ok(Self::Draft),
            1 => Ok(Self::Funding),
            2 => Ok(Self::Active),
            3 => Ok(Self::Settling),
            4 => Ok(Self::Closing),
            5 => Ok(Self::Closed),
            6 => Ok(Self::Expired),
            7 => Ok(Self::Blocked),
            8 => Ok(Self::Disputed),
            9 => Ok(Self::NeedsRecovery),
            10 => Ok(Self::NeedsReview),
            _ => Err(ChannelStateError::UnknownStatus(value)),
        }
    }
}

#[repr(u8)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EnvironmentCode {
    LocalValidator = 0,
    DevnetFixture = 1,
}

impl TryFrom<u8> for EnvironmentCode {
    type Error = ChannelStateError;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            0 => Ok(Self::LocalValidator),
            1 => Ok(Self::DevnetFixture),
            _ => Err(ChannelStateError::UnknownEnvironment(value)),
        }
    }
}

#[repr(u8)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum NetworkCode {
    Solana = 1,
}

impl TryFrom<u8> for NetworkCode {
    type Error = ChannelStateError;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            1 => Ok(Self::Solana),
            _ => Err(ChannelStateError::UnknownNetwork(value)),
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ChannelState {
    pub account_version: u16,
    pub bump: u8,
    pub status: StatusCode,
    pub environment: EnvironmentCode,
    pub network: NetworkCode,
    pub program_version: u16,
    pub policy_flags: u32,
    pub genesis_hash: [u8; 32],
    pub channel_nonce: [u8; 32],
    pub channel_id_hash: [u8; 32],
    pub epoch: u64,
    pub sender: Pubkey,
    pub recipient_claim_pubkey: Pubkey,
    pub recipient_wallet: Pubkey,
    pub recipient_bound: u8,
    pub binding_nonce: [u8; 32],
    pub mint: Pubkey,
    pub vault_token_account: Pubkey,
    pub decimals: u8,
    pub funded_total: u64,
    pub activated_authorized_total: u64,
    pub settled_total: u64,
    pub refunded_total: u64,
    pub latest_activated_sequence: u64,
    pub latest_activated_voucher_hash: [u8; 32],
    pub channel_expiry_set: u8,
    pub channel_expiry: i64,
    pub voucher_expiry_set: u8,
    pub voucher_expiry: i64,
    pub close_requested: u8,
    pub close_requested_at: i64,
    pub claim_deadline_set: u8,
    pub claim_deadline: i64,
    pub reserved: [u8; CHANNEL_STATE_RESERVED_BYTES],
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ChannelStateError {
    WrongProgramOwner,
    WrongLength { expected: usize, actual: usize },
    WrongDiscriminator,
    UnknownVersion(u16),
    UnknownStatus(u8),
    UnknownEnvironment(u8),
    UnknownNetwork(u8),
    UnknownPolicyFlags(u32),
    InvalidBoolean { field: &'static str, value: u8 },
    FlagValueMismatch(&'static str),
    RecipientBindingMismatch,
    ReservedBytesNonZero,
}

impl fmt::Display for ChannelStateError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{self:?}")
    }
}

impl std::error::Error for ChannelStateError {}

pub fn deserialize_program_account(
    input: &[u8],
    actual_owner: &Pubkey,
    expected_program_id: &Pubkey,
) -> Result<ChannelState, ChannelStateError> {
    if actual_owner != expected_program_id {
        return Err(ChannelStateError::WrongProgramOwner);
    }
    ChannelState::deserialize(input)
}

impl ChannelState {
    pub fn validate_structure(&self) -> Result<(), ChannelStateError> {
        if self.account_version != CHANNEL_STATE_VERSION_V1 {
            return Err(ChannelStateError::UnknownVersion(self.account_version));
        }
        if self.policy_flags & !KNOWN_POLICY_FLAGS != 0 {
            return Err(ChannelStateError::UnknownPolicyFlags(self.policy_flags));
        }
        for (field, value) in [
            ("recipient_bound", self.recipient_bound),
            ("channel_expiry_set", self.channel_expiry_set),
            ("voucher_expiry_set", self.voucher_expiry_set),
            ("close_requested", self.close_requested),
            ("claim_deadline_set", self.claim_deadline_set),
        ] {
            validate_boolean(field, value)?;
        }
        if (self.recipient_bound == 0) != (self.recipient_wallet == Pubkey::default()) {
            return Err(ChannelStateError::RecipientBindingMismatch);
        }
        validate_flag_value(
            "channel_expiry",
            self.channel_expiry_set,
            self.channel_expiry,
        )?;
        validate_flag_value(
            "voucher_expiry",
            self.voucher_expiry_set,
            self.voucher_expiry,
        )?;
        validate_flag_value(
            "close_requested_at",
            self.close_requested,
            self.close_requested_at,
        )?;
        validate_flag_value(
            "claim_deadline",
            self.claim_deadline_set,
            self.claim_deadline,
        )?;
        if self.claim_deadline_set == 1 && self.close_requested != 1 {
            return Err(ChannelStateError::FlagValueMismatch("claim_deadline"));
        }
        if self.reserved.iter().any(|byte| *byte != 0) {
            return Err(ChannelStateError::ReservedBytesNonZero);
        }
        Ok(())
    }

    pub fn serialize(&self) -> Result<[u8; CHANNEL_STATE_SPACE], ChannelStateError> {
        self.validate_structure()?;
        let mut output = [0_u8; CHANNEL_STATE_SPACE];
        let mut cursor = Writer::new(&mut output);
        cursor.bytes(&CHANNEL_STATE_DISCRIMINATOR);
        cursor.u16(self.account_version);
        cursor.u8(self.bump);
        cursor.u8(self.status as u8);
        cursor.u8(self.environment as u8);
        cursor.u8(self.network as u8);
        cursor.u16(self.program_version);
        cursor.u32(self.policy_flags);
        cursor.bytes(&self.genesis_hash);
        cursor.bytes(&self.channel_nonce);
        cursor.bytes(&self.channel_id_hash);
        cursor.u64(self.epoch);
        cursor.bytes(self.sender.as_ref());
        cursor.bytes(self.recipient_claim_pubkey.as_ref());
        cursor.bytes(self.recipient_wallet.as_ref());
        cursor.u8(self.recipient_bound);
        cursor.bytes(&self.binding_nonce);
        cursor.bytes(self.mint.as_ref());
        cursor.bytes(self.vault_token_account.as_ref());
        cursor.u8(self.decimals);
        cursor.u64(self.funded_total);
        cursor.u64(self.activated_authorized_total);
        cursor.u64(self.settled_total);
        cursor.u64(self.refunded_total);
        cursor.u64(self.latest_activated_sequence);
        cursor.bytes(&self.latest_activated_voucher_hash);
        cursor.u8(self.channel_expiry_set);
        cursor.i64(self.channel_expiry);
        cursor.u8(self.voucher_expiry_set);
        cursor.i64(self.voucher_expiry);
        cursor.u8(self.close_requested);
        cursor.i64(self.close_requested_at);
        cursor.u8(self.claim_deadline_set);
        cursor.i64(self.claim_deadline);
        cursor.bytes(&self.reserved);
        debug_assert_eq!(cursor.offset, CHANNEL_STATE_SPACE);
        Ok(output)
    }

    pub fn deserialize(input: &[u8]) -> Result<Self, ChannelStateError> {
        if input.len() != CHANNEL_STATE_SPACE {
            return Err(ChannelStateError::WrongLength {
                expected: CHANNEL_STATE_SPACE,
                actual: input.len(),
            });
        }
        let mut cursor = Reader::new(input);
        if cursor.array::<8>() != CHANNEL_STATE_DISCRIMINATOR {
            return Err(ChannelStateError::WrongDiscriminator);
        }
        let account_version = cursor.u16();
        if account_version != CHANNEL_STATE_VERSION_V1 {
            return Err(ChannelStateError::UnknownVersion(account_version));
        }
        let bump = cursor.u8();
        let status = StatusCode::try_from(cursor.u8())?;
        let environment = EnvironmentCode::try_from(cursor.u8())?;
        let network = NetworkCode::try_from(cursor.u8())?;
        let state = Self {
            account_version,
            bump,
            status,
            environment,
            network,
            program_version: cursor.u16(),
            policy_flags: cursor.u32(),
            genesis_hash: cursor.array(),
            channel_nonce: cursor.array(),
            channel_id_hash: cursor.array(),
            epoch: cursor.u64(),
            sender: Pubkey::new_from_array(cursor.array()),
            recipient_claim_pubkey: Pubkey::new_from_array(cursor.array()),
            recipient_wallet: Pubkey::new_from_array(cursor.array()),
            recipient_bound: cursor.u8(),
            binding_nonce: cursor.array(),
            mint: Pubkey::new_from_array(cursor.array()),
            vault_token_account: Pubkey::new_from_array(cursor.array()),
            decimals: cursor.u8(),
            funded_total: cursor.u64(),
            activated_authorized_total: cursor.u64(),
            settled_total: cursor.u64(),
            refunded_total: cursor.u64(),
            latest_activated_sequence: cursor.u64(),
            latest_activated_voucher_hash: cursor.array(),
            channel_expiry_set: cursor.u8(),
            channel_expiry: cursor.i64(),
            voucher_expiry_set: cursor.u8(),
            voucher_expiry: cursor.i64(),
            close_requested: cursor.u8(),
            close_requested_at: cursor.i64(),
            claim_deadline_set: cursor.u8(),
            claim_deadline: cursor.i64(),
            reserved: cursor.array(),
        };
        debug_assert_eq!(cursor.offset, CHANNEL_STATE_SPACE);
        state.validate_structure()?;
        Ok(state)
    }
}

fn validate_boolean(field: &'static str, value: u8) -> Result<(), ChannelStateError> {
    if value > 1 {
        return Err(ChannelStateError::InvalidBoolean { field, value });
    }
    Ok(())
}

fn validate_flag_value(field: &'static str, flag: u8, value: i64) -> Result<(), ChannelStateError> {
    if (flag == 0 && value != 0) || (flag == 1 && value <= 0) {
        return Err(ChannelStateError::FlagValueMismatch(field));
    }
    Ok(())
}

struct Writer<'a> {
    output: &'a mut [u8],
    offset: usize,
}

impl<'a> Writer<'a> {
    fn new(output: &'a mut [u8]) -> Self {
        Self { output, offset: 0 }
    }

    fn bytes(&mut self, value: &[u8]) {
        self.output[self.offset..self.offset + value.len()].copy_from_slice(value);
        self.offset += value.len();
    }

    fn u8(&mut self, value: u8) {
        self.bytes(&[value]);
    }

    fn u16(&mut self, value: u16) {
        self.bytes(&value.to_le_bytes());
    }

    fn u32(&mut self, value: u32) {
        self.bytes(&value.to_le_bytes());
    }

    fn u64(&mut self, value: u64) {
        self.bytes(&value.to_le_bytes());
    }

    fn i64(&mut self, value: i64) {
        self.bytes(&value.to_le_bytes());
    }
}

struct Reader<'a> {
    input: &'a [u8],
    offset: usize,
}

impl<'a> Reader<'a> {
    fn new(input: &'a [u8]) -> Self {
        Self { input, offset: 0 }
    }

    fn array<const N: usize>(&mut self) -> [u8; N] {
        let value = self.input[self.offset..self.offset + N]
            .try_into()
            .expect("fixed-width reader is length checked before decoding");
        self.offset += N;
        value
    }

    fn u8(&mut self) -> u8 {
        self.array::<1>()[0]
    }

    fn u16(&mut self) -> u16 {
        u16::from_le_bytes(self.array())
    }

    fn u32(&mut self) -> u32 {
        u32::from_le_bytes(self.array())
    }

    fn u64(&mut self) -> u64 {
        u64::from_le_bytes(self.array())
    }

    fn i64(&mut self) -> i64 {
        i64::from_le_bytes(self.array())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state() -> ChannelState {
        ChannelState {
            account_version: CHANNEL_STATE_VERSION_V1,
            bump: 255,
            status: StatusCode::Draft,
            environment: EnvironmentCode::LocalValidator,
            network: NetworkCode::Solana,
            program_version: 1,
            policy_flags: 0,
            genesis_hash: [1; 32],
            channel_nonce: [2; 32],
            channel_id_hash: [3; 32],
            epoch: 0,
            sender: Pubkey::new_from_array([4; 32]),
            recipient_claim_pubkey: Pubkey::new_from_array([5; 32]),
            recipient_wallet: Pubkey::default(),
            recipient_bound: 0,
            binding_nonce: [6; 32],
            mint: Pubkey::new_from_array([7; 32]),
            vault_token_account: Pubkey::new_from_array([8; 32]),
            decimals: 6,
            funded_total: 0,
            activated_authorized_total: 0,
            settled_total: 0,
            refunded_total: 0,
            latest_activated_sequence: 0,
            latest_activated_voucher_hash: [0; 32],
            channel_expiry_set: 0,
            channel_expiry: 0,
            voucher_expiry_set: 0,
            voucher_expiry: 0,
            close_requested: 0,
            close_requested_at: 0,
            claim_deadline_set: 0,
            claim_deadline: 0,
            reserved: [0; CHANNEL_STATE_RESERVED_BYTES],
        }
    }

    #[test]
    fn fixed_width_round_trip() {
        let original = state();
        let encoded = original.serialize().unwrap();
        assert_eq!(encoded.len(), CHANNEL_STATE_SPACE);
        assert_eq!(ChannelState::deserialize(&encoded).unwrap(), original);
        let mut expected_offset = 0;
        for (_, offset, width) in CHANNEL_STATE_FIELDS {
            assert_eq!(*offset, expected_offset);
            expected_offset += width;
        }
        assert_eq!(expected_offset, CHANNEL_STATE_SPACE);
    }

    #[test]
    fn rejects_unknown_version_status_and_nonzero_reserved() {
        let encoded = state().serialize().unwrap();

        let mut discriminator = encoded;
        discriminator[0] ^= 1;
        assert_eq!(
            ChannelState::deserialize(&discriminator),
            Err(ChannelStateError::WrongDiscriminator)
        );

        let mut wrong_version = encoded;
        wrong_version[8..10].copy_from_slice(&2_u16.to_le_bytes());
        assert_eq!(
            ChannelState::deserialize(&wrong_version),
            Err(ChannelStateError::UnknownVersion(2))
        );

        let mut wrong_status = encoded;
        wrong_status[11] = 255;
        assert_eq!(
            ChannelState::deserialize(&wrong_status),
            Err(ChannelStateError::UnknownStatus(255))
        );

        let mut reserved = encoded;
        reserved[CHANNEL_STATE_SPACE - 1] = 1;
        assert_eq!(
            ChannelState::deserialize(&reserved),
            Err(ChannelStateError::ReservedBytesNonZero)
        );
    }

    #[test]
    fn rejects_unknown_codes_flags_and_flag_value_mismatches() {
        let encoded = state().serialize().unwrap();

        let cases = [
            (12, 255, ChannelStateError::UnknownEnvironment(255)),
            (13, 255, ChannelStateError::UnknownNetwork(255)),
            (
                16,
                4,
                ChannelStateError::UnknownPolicyFlags(u32::from_le_bytes([4, 0, 0, 0])),
            ),
            (
                220,
                2,
                ChannelStateError::InvalidBoolean {
                    field: "recipient_bound",
                    value: 2,
                },
            ),
            (
                390,
                2,
                ChannelStateError::InvalidBoolean {
                    field: "channel_expiry_set",
                    value: 2,
                },
            ),
        ];
        for (offset, value, expected) in cases {
            let mut candidate = encoded;
            candidate[offset] = value;
            assert_eq!(ChannelState::deserialize(&candidate), Err(expected));
        }

        let mut expiry_without_flag = encoded;
        expiry_without_flag[391..399].copy_from_slice(&1_i64.to_le_bytes());
        assert_eq!(
            ChannelState::deserialize(&expiry_without_flag),
            Err(ChannelStateError::FlagValueMismatch("channel_expiry"))
        );

        let mut deadline_without_close = encoded;
        deadline_without_close[417] = 1;
        deadline_without_close[418..426].copy_from_slice(&1_i64.to_le_bytes());
        assert_eq!(
            ChannelState::deserialize(&deadline_without_close),
            Err(ChannelStateError::FlagValueMismatch("claim_deadline"))
        );
    }

    #[test]
    fn rejects_wrong_program_owner_before_decoding() {
        let program_id = Pubkey::new_from_array([9; 32]);
        let wrong_owner = Pubkey::new_from_array([10; 32]);
        let encoded = state().serialize().unwrap();
        assert_eq!(
            deserialize_program_account(&encoded, &wrong_owner, &program_id),
            Err(ChannelStateError::WrongProgramOwner)
        );
        assert_eq!(
            deserialize_program_account(&encoded, &program_id, &program_id),
            Ok(state())
        );
    }

    #[test]
    fn rejects_unauthorized_lengths_and_binding_inconsistency() {
        let encoded = state().serialize().unwrap();
        assert!(matches!(
            ChannelState::deserialize(&encoded[..CHANNEL_STATE_SPACE - 1]),
            Err(ChannelStateError::WrongLength { .. })
        ));
        let mut long = encoded.to_vec();
        long.push(0);
        assert!(matches!(
            ChannelState::deserialize(&long),
            Err(ChannelStateError::WrongLength { .. })
        ));

        let mut invalid = state();
        invalid.recipient_bound = 1;
        assert_eq!(
            invalid.serialize(),
            Err(ChannelStateError::RecipientBindingMismatch)
        );
    }
}
