#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
RUNTIME_DIR="$ROOT/tests/channels/solana/runtime"
PROGRAM_MANIFEST="$ROOT/programs/foundry-channel-vault/program/Cargo.toml"
AGAVE_VERSION="v2.1.21"
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
  fi
  rm -rf "$TMP"
  exit "$status"
}
trap cleanup EXIT

export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"

stage "agave-install"
if ! command -v solana >/dev/null 2>&1 || ! solana --version | grep -q '2\.1\.21'; then
  curl -sSfL "https://release.anza.xyz/${AGAVE_VERSION}/install" | sh
  export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
fi

stage "toolchain-check"
solana --version | grep -q '2\.1\.21'
command -v solana-test-validator >/dev/null
command -v cargo-build-sbf >/dev/null
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
export NODE_OPTIONS="--dns-result-order=ipv4first"

stage "validator-phase1-start"
start_phase1_validator
stage "validator-phase1-client"
node "$RUNTIME_DIR/validator-client.mjs" phase1 | tee "$PHASE1_OUT"
stop_validator

CLOSE_SLOT="$(node -e "const c=require(process.argv[1]); process.stdout.write(String(c.slot));" "$CONTEXT")"
WARP_SLOT="$((CLOSE_SLOT + 100000))"

stage "validator-phase2-start"
start_phase2_validator "$WARP_SLOT"
stage "validator-phase2-client"
node "$RUNTIME_DIR/validator-client.mjs" phase2 | tee "$PHASE2_OUT"
stop_validator

stage "receipt"
export SBF_SHA256 WARP_SLOT PHASE1_OUT PHASE2_OUT PLATFORM_TOOLS_VERSION
node <<'NODE'
const fs = require('node:fs');
const lastJson = (path) => {
  const lines = fs.readFileSync(path, 'utf8').trim().split(/\r?\n/);
  return JSON.parse(lines.reverse().find((line) => line.startsWith('{')));
};
const phase1 = lastJson(process.env.PHASE1_OUT);
const phase2 = lastJson(process.env.PHASE2_OUT);
process.stdout.write(JSON.stringify({
  ok: true,
  agaveVersion: 'v2.1.21',
  platformToolsVersion: process.env.PLATFORM_TOOLS_VERSION,
  programIdScope: 'ephemeral_local_validator_only',
  programId: '11111111111111111111111111111112',
  sbfSha256: process.env.SBF_SHA256,
  warpSlot: Number(process.env.WARP_SLOT),
  phase1,
  phase2,
  claimsNotAuthorized: ['devnet_deployment', 'mainnet', 'real_value'],
}) + '\n');
NODE
