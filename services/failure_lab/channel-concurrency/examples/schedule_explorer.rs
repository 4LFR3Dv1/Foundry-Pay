use foundry_channel_concurrency_model::{
    vault_conservation_holds, ConcurrencyError, LinearizationHarness,
};
use foundry_channel_vault_transition_model::{
    apply, canonical_recipient_ata, ModelInstruction, ModelState,
};
use serde::Serialize;
use std::{env, fmt::Write, fs, path::Path};

#[derive(Clone)]
struct Scenario {
    name: &'static str,
    state: ModelState,
    first_id: [u8; 32],
    first: ModelInstruction,
    first_prepare_time: i64,
    first_commit_time: i64,
    second_id: [u8; 32],
    second: ModelInstruction,
    second_prepare_time: i64,
    second_commit_time: i64,
}

#[derive(Serialize)]
struct ScheduleResult {
    scenario: &'static str,
    commit_order: [usize; 2],
    prepared_count: usize,
    accepted_count: usize,
    stale_count: usize,
    duplicate_count: usize,
    model_rejection_count: usize,
    accepted_order: Vec<String>,
    final_version: u64,
    final_settled: u64,
    final_refunded: u64,
    final_activated: u64,
    serial_witness: bool,
    conservation: bool,
}

#[derive(Serialize)]
struct Report {
    work_item: &'static str,
    claim: &'static str,
    scenarios: usize,
    schedules: usize,
    violations: usize,
    results: Vec<ScheduleResult>,
}

fn main() {
    let output = env::args()
        .nth(1)
        .expect("usage: schedule_explorer <output.json>");
    let scenarios = scenarios();
    let mut results = Vec::new();
    for scenario in &scenarios {
        for order in [[0, 1], [1, 0]] {
            results.push(run_schedule(scenario, order));
        }
    }
    let violations = results
        .iter()
        .filter(|result| !result.serial_witness || !result.conservation)
        .count();
    let report = Report {
        work_item: "FC-SEC-004",
        claim: "offline concurrent candidates were checked for conditional commit, stale rejection, conservation, and serial witnesses",
        scenarios: scenarios.len(),
        schedules: results.len(),
        violations,
        results,
    };
    fs::write(
        Path::new(&output),
        [serde_json::to_vec_pretty(&report).unwrap(), b"\n".to_vec()].concat(),
    )
    .unwrap();
}

fn run_schedule(scenario: &Scenario, order: [usize; 2]) -> ScheduleResult {
    let mut harness = LinearizationHarness::new(scenario.state.clone()).unwrap();
    let candidates = [
        harness.prepare(
            scenario.first_id,
            scenario.first.clone(),
            scenario.first_prepare_time,
        ),
        harness.prepare(
            scenario.second_id,
            scenario.second.clone(),
            scenario.second_prepare_time,
        ),
    ];
    let prepared_count = candidates.iter().filter(|result| result.is_ok()).count();
    let mut accepted = 0;
    let mut stale = 0;
    let mut duplicate = 0;
    let mut model_rejections = candidates.iter().filter(|result| result.is_err()).count();
    for index in order {
        let Ok(candidate) = candidates[index].clone() else {
            continue;
        };
        let commit_time = if index == 0 {
            scenario.first_commit_time
        } else {
            scenario.second_commit_time
        };
        match harness.commit(candidate, commit_time) {
            Ok(_) => accepted += 1,
            Err(ConcurrencyError::StaleSnapshot) => stale += 1,
            Err(ConcurrencyError::DuplicateOperation) => duplicate += 1,
            Err(ConcurrencyError::Model(_)) => model_rejections += 1,
            Err(_) => model_rejections += 1,
        }
    }
    let snapshot = harness.snapshot();
    let accepted_order = harness
        .history()
        .iter()
        .map(|record| to_hex(record.instruction_id))
        .collect();
    ScheduleResult {
        scenario: scenario.name,
        commit_order: order,
        prepared_count,
        accepted_count: accepted,
        stale_count: stale,
        duplicate_count: duplicate,
        model_rejection_count: model_rejections,
        accepted_order,
        final_version: snapshot.version,
        final_settled: snapshot.state.settled,
        final_refunded: snapshot.state.refunded,
        final_activated: snapshot.state.activated,
        serial_witness: harness.verify_serial_witness().is_ok(),
        conservation: snapshot.state.invariants_hold() && vault_conservation_holds(&snapshot.state),
    }
}

fn scenarios() -> Vec<Scenario> {
    let active_40 = active(100, 40, 0);
    let closing_40 = closing(100, 40, 0, 900);
    vec![
        Scenario {
            name: "settle_30_vs_settle_30",
            state: active_40.clone(),
            first_id: key(20),
            first: settlement(&active_40, 1, 30),
            first_prepare_time: 1,
            first_commit_time: 1,
            second_id: key(21),
            second: settlement(&active_40, 2, 30),
            second_prepare_time: 1,
            second_commit_time: 1,
        },
        Scenario {
            name: "settle_10_vs_settle_30",
            state: active_40.clone(),
            first_id: key(22),
            first: settlement(&active_40, 1, 10),
            first_prepare_time: 1,
            first_commit_time: 1,
            second_id: key(23),
            second: settlement(&active_40, 2, 30),
            second_prepare_time: 1,
            second_commit_time: 1,
        },
        Scenario {
            name: "duplicate_settlement_id",
            state: active_40.clone(),
            first_id: key(24),
            first: settlement(&active_40, 1, 20),
            first_prepare_time: 1,
            first_commit_time: 1,
            second_id: key(24),
            second: settlement(&active_40, 2, 20),
            second_prepare_time: 1,
            second_commit_time: 1,
        },
        Scenario {
            name: "refund_60_vs_settle_40",
            state: closing_40.clone(),
            first_id: key(30),
            first: ModelInstruction::RefundUnallocated { amount: 60 },
            first_prepare_time: 900,
            first_commit_time: 900,
            second_id: key(31),
            second: settlement(&closing_40, 2, 40),
            second_prepare_time: 900,
            second_commit_time: 900,
        },
        Scenario {
            name: "activation_pre_deadline_vs_refund_at_deadline",
            state: closing_40.clone(),
            first_id: key(40),
            first: ModelInstruction::Activate {
                sequence: 2,
                cumulative_authorized: 70,
                voucher_expiry: 2_000,
            },
            first_prepare_time: 899,
            first_commit_time: 900,
            second_id: key(41),
            second: ModelInstruction::RefundUnallocated { amount: 60 },
            second_prepare_time: 900,
            second_commit_time: 900,
        },
        Scenario {
            name: "close_vs_activation",
            state: active_40.clone(),
            first_id: key(50),
            first: ModelInstruction::RequestClose {
                claim_deadline: 900,
            },
            first_prepare_time: 0,
            first_commit_time: 0,
            second_id: key(51),
            second: ModelInstruction::Activate {
                sequence: 2,
                cumulative_authorized: 70,
                voucher_expiry: 2_000,
            },
            second_prepare_time: 0,
            second_commit_time: 1,
        },
        Scenario {
            name: "same_sequence_activation",
            state: active_40.clone(),
            first_id: key(60),
            first: ModelInstruction::Activate {
                sequence: 2,
                cumulative_authorized: 60,
                voucher_expiry: 2_000,
            },
            first_prepare_time: 0,
            first_commit_time: 0,
            second_id: key(61),
            second: ModelInstruction::Activate {
                sequence: 2,
                cumulative_authorized: 70,
                voucher_expiry: 2_000,
            },
            second_prepare_time: 0,
            second_commit_time: 0,
        },
    ]
}

fn active(funded: u64, activated: u64, settled: u64) -> ModelState {
    let mut state = apply(
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
    .state;
    state = apply(&state, &ModelInstruction::Fund { amount: funded }, 0)
        .unwrap()
        .state;
    state = apply(
        &state,
        &ModelInstruction::Activate {
            sequence: 1,
            cumulative_authorized: activated,
            voucher_expiry: 10_000,
        },
        0,
    )
    .unwrap()
    .state;
    state = apply(
        &state,
        &ModelInstruction::BindRecipient { recipient: key(9) },
        0,
    )
    .unwrap()
    .state;
    if settled > 0 {
        let operation = settlement(&state, 10, settled);
        state = apply(&state, &operation, 0).unwrap().state;
    }
    state
}

fn closing(funded: u64, activated: u64, settled: u64, deadline: i64) -> ModelState {
    apply(
        &active(funded, activated, settled),
        &ModelInstruction::RequestClose {
            claim_deadline: deadline,
        },
        0,
    )
    .unwrap()
    .state
}

fn settlement(state: &ModelState, caller: u8, amount: u64) -> ModelInstruction {
    ModelInstruction::Settle {
        caller: key(caller),
        amount,
        obligation_hash: key(caller.wrapping_add(1)),
        supplied_destination: canonical_recipient_ata(state.bound_recipient, state.mint),
    }
}

fn key(value: u8) -> [u8; 32] {
    [value; 32]
}

fn to_hex(value: [u8; 32]) -> String {
    value
        .iter()
        .fold(String::with_capacity(64), |mut hex, byte| {
            write!(hex, "{byte:02x}").expect("writing to String cannot fail");
            hex
        })
}
