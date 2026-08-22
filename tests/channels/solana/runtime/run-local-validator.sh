#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
RUNTIME_DIR="$ROOT/tests/channels/solana/runtime"
PROGRAM_MANIFEST="$ROOT/programs/foundry-channel-vault/program/Cargo.toml"
BUILD_AGAVE_VERSION="v3.1.5"
VALIDATOR_AGAVE_VERSION="${FC_SOL_006_VALIDATOR_AGAVE_VERSION:-v2.1.21}"
VALIDATOR_VERSION="${VALIDATOR_AGAVE_VERSION#v}"
PLATFORM_TOOLS_VERSION="v1.52"
PROGRAM_ID="11111111111111111111111111111112"
RPC_PORT="${FC_SOL_006_RPC_PORT:-18999}"
RPC="http://127.0.0.1:${RPC_PORT}"
TMP="$(mktemp -d)"
LEDGER="$TMP/ledger"
CONTEXT="$TMP/validator-context.json"
SBF_DIR="$TMP/sbf"
PHASE1_OUT="$TMP/phase1.out"
PHASE2_OUT="$TMP/phase2.out"
VALIDATOR_PID=""
CURRENT_STAGE="bootstrap"
ACTIVE_BIN="$HOME/.local/share/solana/install/active_release/bin"

stage() {
  CURRENT_STAGE="$1"
  echo "FC-SOL-006 stage=$CURRENT_STAGE"
}

cleanup() {
  local status=$?
  if [[ -n "$VALIDATOR_PID" ]] && kill -0 "$VALIDATOR_PID" 2>/dev/null; then
    kill "$VALIDATOR_PID" 2>/dev/null || true
    wait "$VALIDATOR_PID" 2>/dev/null || true
  fi
  if [[ $status -ne 0 ]]; then
    echo "FC-SOL-006 failed stage=$CURRENT_STAGE status=$status" >&2
    for log in cargo-build-sbf.log validator.log npm-install.log phase1.out phase2.out; do
      if [[ -s "$TMP/$log" ]]; then
        echo "----- $log -----" >&2
        tail -400 "$TMP/$log" >&2 || true
      fi
    done
    if [[ -s "$LEDGER/validator.log" ]]; then
      echo "----- ledger/validator.log transport diagnostics -----" >&2
      grep -E -i \
        'transaction|packet|tpu|sanitize|sanitiz|cost|address.?lookup|lookup.?table|blockhash|signature|drop|discard|forward|bank|error|fail' \
        "$LEDGER/validator.log" | tail -600 >&2 || true
      echo "----- ledger/validator.log tail -----" >&2
      tail -400 "$LEDGER/validator.log" >&2 || true
    fi
  fi
  rm -rf "$TMP"
  exit "$status"
}
trap cleanup EXIT

export PATH="$ACTIVE_BIN:$PATH"

install_agave() {
  local version="$1"
  curl -sSfL "https://release.anza.xyz/${version}/install" | sh
  export PATH="$ACTIVE_BIN:$PATH"
}

stage "toolchain-check"
command -v node >/dev/null
command -v npm >/dev/null

stage "validator-client-install"
if ! npm install \
  --prefix "$RUNTIME_DIR" \
  --ignore-scripts \
  --no-audit \
  --no-fund \
  --no-package-lock >"$TMP/npm-install.log" 2>&1; then
  cat "$TMP/npm-install.log" >&2
  exit 1
fi

# Build and runtime are intentionally pinned independently. The program still
# depends on solana-program 2.1.21, while the SBF compiler must satisfy the
# repository's Rust 1.85.1 MSRV. Agave 3.1.5 ships cargo-build-sbf with
# platform-tools v1.52; the executable artifact is then run against the
# selected local validator version.
stage "build-agave-install"
if ! command -v solana >/dev/null 2>&1 || ! solana --version | grep -q '3\.1\.5'; then
  install_agave "$BUILD_AGAVE_VERSION"
fi
solana --version | grep -q '3\.1\.5'
command -v cargo-build-sbf >/dev/null
cargo-build-sbf --version | tee "$TMP/cargo-build-sbf-version.log"
grep -q '3\.1\.5' "$TMP/cargo-build-sbf-version.log"
grep -q 'platform-tools v1\.52' "$TMP/cargo-build-sbf-version.log"

stage "cargo-build-sbf"
mkdir -p "$SBF_DIR"
if ! cargo-build-sbf \
  --tools-version "$PLATFORM_TOOLS_VERSION" \
  --manifest-path "$PROGRAM_MANIFEST" \
  --sbf-out-dir "$SBF_DIR" \
  >"$TMP/cargo-build-sbf.log" 2>&1; then
  cat "$TMP/cargo-build-sbf.log" >&2
  exit 1
fi

ARTIFACT="$SBF_DIR/foundry_channel_vault_program.so"
test -f "$ARTIFACT"
SBF_SHA256="$(sha256sum "$ARTIFACT" | awk '{print $1}')"

stage "validator-agave-install"
if ! solana --version | grep -q "${VALIDATOR_VERSION//./\\.}"; then
  install_agave "$VALIDATOR_AGAVE_VERSION"
fi
solana --version | grep -q "${VALIDATOR_VERSION//./\\.}"
command -v solana-test-validator >/dev/null

wait_rpc() {
  local attempt
  for attempt in $(seq 1 360); do
    if ! kill -0 "$VALIDATOR_PID" 2>/dev/null; then
      tail -200 "$TMP/validator.log" >&2 || true
      echo "solana-test-validator exited before RPC became healthy" >&2
      exit 1
    fi
    if curl -sS \
      -H 'content-type: application/json' \
      --data '{"jsonrpc":"2.0","id":1,"method":"getHealth"}' \
      "$RPC" 2>/dev/null | grep -q '"result":"ok"'; then
      return 0
    fi
    sleep 0.25
  done
  tail -200 "$TMP/validator.log" >&2 || true
  echo "solana-test-validator RPC did not become healthy" >&2
  exit 1
}

stop_validator() {
  if [[ -n "$VALIDATOR_PID" ]] && kill -0 "$VALIDATOR_PID" 2>/dev/null; then
    kill "$VALIDATOR_PID"
    wait "$VALIDATOR_PID" 2>/dev/null || true
  fi
  VALIDATOR_PID=""
}

start_phase1_validator() {
  : >"$TMP/validator.log"
  solana-test-validator \
    --ledger "$LEDGER" \
    --reset \
    --rpc-port "$RPC_PORT" \
    --bind-address 127.0.0.1 \
    --bpf-program "$PROGRAM_ID" "$ARTIFACT" \
    >>"$TMP/validator.log" 2>&1 &
  VALIDATOR_PID="$!"
  wait_rpc
}

start_phase2_validator() {
  local warp_slot="$1"
  : >"$TMP/validator.log"
  solana-test-validator \
    --ledger "$LEDGER" \
    --rpc-port "$RPC_PORT" \
    --bind-address 127.0.0.1 \
    --warp-slot "$warp_slot" \
    >>"$TMP/validator.log" 2>&1 &
  VALIDATOR_PID="$!"
  wait_rpc
}

export FC_SOL_006_RPC="$RPC"
export FC_SOL_006_PROGRAM_ID="$PROGRAM_ID"
export FC_SOL_006_CONTEXT="$CONTEXT"
export FC_SOL_006_VALIDATOR_LOG="$LEDGER/validator.log"
export NODE_OPTIONS="--dns-result-order=ipv4first"
CONTROLS_ONLY="${FC_SOL_006_TRANSPORT_CONTROLS_ONLY:-0}"
BIND_PROBE_ONLY="${FC_SOL_006_BIND_COMPUTE_PROBE:-0}"

stage "validator-phase1-start"
start_phase1_validator
stage "validator-phase1-client"
node "$RUNTIME_DIR/validator-client-runner.mjs" phase1 | tee "$PHASE1_OUT"
stop_validator

if [[ "$CONTROLS_ONLY" != "1" && "$BIND_PROBE_ONLY" != "1" ]]; then
  FULL_SNAPSHOT_SLOT="$(node -e "const c=require(process.argv[1]); process.stdout.write(String(c.snapshotBoundary.fullSnapshotSlot));" "$CONTEXT")"
  WARP_SLOT="$((FULL_SNAPSHOT_SLOT + 100000))"

  stage "validator-phase2-start"
  start_phase2_validator "$WARP_SLOT"
  stage "validator-phase2-client"
  node "$RUNTIME_DIR/validator-client-runner.mjs" phase2 | tee "$PHASE2_OUT"
  stop_validator
else
  WARP_SLOT="0"
  : >"$PHASE2_OUT"
fi

stage "receipt"
export SBF_SHA256 WARP_SLOT PHASE1_OUT PHASE2_OUT PLATFORM_TOOLS_VERSION \
  BUILD_AGAVE_VERSION VALIDATOR_AGAVE_VERSION
node <<'NODE'
const fs = require('node:fs');
const lastJson = (path) => {
  const lines = fs.readFileSync(path, 'utf8').trim().split(/\r?\n/);
  return JSON.parse(lines.reverse().find((line) => line.startsWith('{')));
};
const phase1 = lastJson(process.env.PHASE1_OUT);
const phase2Lines = fs.readFileSync(process.env.PHASE2_OUT, 'utf8').trim();
const phase2 = phase2Lines ? lastJson(process.env.PHASE2_OUT) : null;
process.stdout.write(JSON.stringify({
  ok: true,
  agaveVersion: process.env.VALIDATOR_AGAVE_VERSION,
  sbfBuildAgaveVersion: process.env.BUILD_AGAVE_VERSION,
  validatorAgaveVersion: process.env.VALIDATOR_AGAVE_VERSION,
  platformToolsVersion: process.env.PLATFORM_TOOLS_VERSION,
  programSdkVersion: '2.1.21',
  programIdScope: 'ephemeral_local_validator_only',
  programId: '11111111111111111111111111111112',
  sbfSha256: process.env.SBF_SHA256,
  warpSlot: Number(process.env.WARP_SLOT),
  phase1,
  phase2,
  claimsNotAuthorized: ['devnet_deployment', 'mainnet', 'real_value'],
}) + '\n');
NODE
