use solana_pubkey::Pubkey;

pub const CHANNEL_SEED: &[u8] = b"channel";

pub fn derive_channel_pda(
    program_id: &Pubkey,
    sender: &Pubkey,
    mint: &Pubkey,
    channel_nonce: &[u8; 32],
) -> (Pubkey, u8) {
    Pubkey::find_program_address(
        &[CHANNEL_SEED, sender.as_ref(), mint.as_ref(), channel_nonce],
        program_id,
    )
}

pub fn verify_channel_pda(
    expected: &Pubkey,
    expected_bump: u8,
    program_id: &Pubkey,
    sender: &Pubkey,
    mint: &Pubkey,
    channel_nonce: &[u8; 32],
) -> bool {
    derive_channel_pda(program_id, sender, mint, channel_nonce) == (*expected, expected_bump)
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    proptest! {
        #[test]
        fn pda_is_deterministic_and_one_field_mutations_change_it(
            program in any::<[u8; 32]>(),
            sender in any::<[u8; 32]>(),
            mint in any::<[u8; 32]>(),
            nonce in any::<[u8; 32]>(),
        ) {
            let program = Pubkey::new_from_array(program);
            let sender = Pubkey::new_from_array(sender);
            let mint = Pubkey::new_from_array(mint);
            let first = derive_channel_pda(&program, &sender, &mint, &nonce);
            let second = derive_channel_pda(&program, &sender, &mint, &nonce);
            prop_assert_eq!(first, second);

            let mut mutated_nonce = nonce;
            mutated_nonce[0] ^= 1;
            prop_assert_ne!(
                first.0,
                derive_channel_pda(&program, &sender, &mint, &mutated_nonce).0
            );

            let mut mutated_sender = sender.to_bytes();
            mutated_sender[0] ^= 1;
            prop_assert_ne!(
                first.0,
                derive_channel_pda(
                    &program,
                    &Pubkey::new_from_array(mutated_sender),
                    &mint,
                    &nonce
                ).0
            );

            let mut mutated_mint = mint.to_bytes();
            mutated_mint[0] ^= 1;
            prop_assert_ne!(
                first.0,
                derive_channel_pda(
                    &program,
                    &sender,
                    &Pubkey::new_from_array(mutated_mint),
                    &nonce
                ).0
            );

            let mut mutated_program = program.to_bytes();
            mutated_program[0] ^= 1;
            prop_assert_ne!(
                first.0,
                derive_channel_pda(
                    &Pubkey::new_from_array(mutated_program),
                    &sender,
                    &mint,
                    &nonce
                ).0
            );
        }
    }
}
