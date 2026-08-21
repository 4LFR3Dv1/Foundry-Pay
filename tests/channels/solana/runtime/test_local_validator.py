from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[4]
RUNTIME_DIR = Path(__file__).parent
PROGRAM_MANIFEST = ROOT / "programs" / "foundry-channel-vault" / "program" / "Cargo.toml"
AGAVE_VERSION = "v2.1.21"
LOCAL_PROGRAM_ID = "11111111111111111111111111111112"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _rpc(url: str, method: str, params: list[object] | None = None) -> object:
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
    ).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(  # noqa: S310 - loopback RPC only
        request, timeout=3
    ) as response:
        payload = json.loads(response.read())
    if "error" in payload:
        raise RuntimeError(f"RPC {method} failed: {payload['error']}")
    return payload["result"]


def _wait_for_rpc(
    url: str, process: subprocess.Popen[str], log_path: Path
) -> None:
    deadline = time.monotonic() + 90
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-12000:]
            raise AssertionError(
                f"solana-test-validator exited {process.returncode}\n{tail}"
            )
        try:
            if _rpc(url, "getHealth") == "ok":
                return
        except Exception as exc:  # validator is still starting
            last_error = exc
        time.sleep(0.25)
    tail = log_path.read_text(encoding="utf-8", errors="replace")[-12000:]
    raise AssertionError(
        f"validator RPC never became healthy: {last_error}\n{tail}"
    )


def _install_agave_if_needed(tmp_path: Path) -> tuple[dict[str, str], Path]:
    env = os.environ.copy()
    installed_bin = (
        Path.home()
        / ".local"
        / "share"
        / "solana"
        / "install"
        / "active_release"
        / "bin"
    )
    env["PATH"] = os.pathsep.join([str(installed_bin), env.get("PATH", "")])

    validator = shutil.which("solana-test-validator", path=env["PATH"])
    solana = shutil.which("solana", path=env["PATH"])
    if validator and solana:
        version = subprocess.run(
            [solana, "--version"],
            check=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        ).stdout
        if "2.1.21" in version:
            return env, Path(validator)

    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        and os.environ.get("FC_SOL_006_RUN_VALIDATOR") != "1"
    ):
        pytest.skip(
            "FC-SOL-006 real validator suite requires Agave 2.1.21; set "
            "FC_SOL_006_RUN_VALIDATOR=1 to bootstrap it outside GitHub Actions"
        )

    installer_log = tmp_path / "agave-install.log"
    completed = subprocess.run(
        [
            "sh",
            "-c",
            f"curl -sSfL https://release.anza.xyz/{AGAVE_VERSION}/install | sh",
        ],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=360,
    )
    installer_log.write_text(
        completed.stdout + "\n" + completed.stderr, encoding="utf-8"
    )
    assert completed.returncode == 0, installer_log.read_text(encoding="utf-8")

    validator = shutil.which("solana-test-validator", path=env["PATH"])
    solana = shutil.which("solana", path=env["PATH"])
    cargo_build_sbf = shutil.which("cargo-build-sbf", path=env["PATH"])
    assert validator and solana and cargo_build_sbf, installer_log.read_text(
        encoding="utf-8"
    )
    version = subprocess.run(
        [solana, "--version"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    ).stdout
    assert "2.1.21" in version, version
    return env, Path(validator)


def _install_validator_client(env: dict[str, str]) -> None:
    node = shutil.which("node", path=env["PATH"])
    npm = shutil.which("npm", path=env["PATH"])
    if not node or not npm:
        pytest.skip("Node/npm are required for the FC-SOL-006 validator client")
    completed = subprocess.run(
        [
            npm,
            "install",
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
            "--no-package-lock",
        ],
        cwd=RUNTIME_DIR,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr


def _build_sbf(tmp_path: Path, env: dict[str, str]) -> tuple[Path, str]:
    out_dir = tmp_path / "sbf"
    out_dir.mkdir()
    cargo_build_sbf = shutil.which("cargo-build-sbf", path=env["PATH"])
    assert cargo_build_sbf
    completed = subprocess.run(
        [
            cargo_build_sbf,
            "--manifest-path",
            str(PROGRAM_MANIFEST),
            "--sbf-out-dir",
            str(out_dir),
        ],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    build_log = tmp_path / "cargo-build-sbf.log"
    build_log.write_text(
        completed.stdout + "\n" + completed.stderr, encoding="utf-8"
    )
    assert completed.returncode == 0, build_log.read_text(encoding="utf-8")
    artifact = out_dir / "foundry_channel_vault_program.so"
    assert artifact.is_file(), sorted(path.name for path in out_dir.iterdir())
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    return artifact, digest


@contextmanager
def _validator(
    validator: Path,
    env: dict[str, str],
    ledger: Path,
    rpc_port: int,
    log_path: Path,
    artifact: Path,
    *,
    reset: bool,
    warp_slot: int | None = None,
):
    command = [
        str(validator),
        "--ledger",
        str(ledger),
        "--rpc-port",
        str(rpc_port),
        "--bind-address",
        "127.0.0.1",
    ]
    if reset:
        command.extend(
            ["--reset", "--bpf-program", LOCAL_PROGRAM_ID, str(artifact)]
        )
    if warp_slot is not None:
        command.extend(["--warp-slot", str(warp_slot)])

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(  # noqa: S603 - fixed local test binary/args
            command,
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            url = f"http://127.0.0.1:{rpc_port}"
            _wait_for_rpc(url, process, log_path)
            yield url
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


def _run_client(
    env: dict[str, str], rpc: str, context: Path, phase: str
) -> dict[str, object]:
    node = shutil.which("node", path=env["PATH"])
    assert node
    client_env = env.copy()
    client_env.update(
        {
            "FC_SOL_006_RPC": rpc,
            "FC_SOL_006_PROGRAM_ID": LOCAL_PROGRAM_ID,
            "FC_SOL_006_CONTEXT": str(context),
            "NODE_OPTIONS": "--dns-result-order=ipv4first",
        }
    )
    completed = subprocess.run(
        [node, str(RUNTIME_DIR / "validator-client.mjs"), phase],
        cwd=RUNTIME_DIR,
        env=client_env,
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    lines = [line for line in completed.stdout.splitlines() if line.startswith("{")]
    assert lines, completed.stdout
    return json.loads(lines[-1])


def test_real_solana_test_validator_lifecycle(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip(
            "solana-test-validator is not a reliable native-Windows FC-SOL-006 target"
        )

    env, validator = _install_agave_if_needed(tmp_path)
    _install_validator_client(env)
    artifact, artifact_sha256 = _build_sbf(tmp_path, env)

    ledger = tmp_path / "ledger"
    context = tmp_path / "validator-context.json"
    rpc_port = _free_port()

    with _validator(
        validator,
        env,
        ledger,
        rpc_port,
        tmp_path / "validator-phase1.log",
        artifact,
        reset=True,
    ) as rpc:
        phase1 = _run_client(env, rpc, context, "phase1")
        slot = int(_rpc(rpc, "getSlot", [{"commitment": "confirmed"}]))

    assert phase1["bindingEd25519Data"] < 1_232
    assert phase1["bindRecipient"] <= 1_232
    assert phase1["activateVoucher"] <= 1_232

    saved = json.loads(context.read_text(encoding="utf-8"))
    deadline = int(saved["claimDeadline"])
    warp_slot = max(slot, int(saved["slot"])) + 100_000

    with _validator(
        validator,
        env,
        ledger,
        rpc_port,
        tmp_path / "validator-phase2.log",
        artifact,
        reset=False,
        warp_slot=warp_slot,
    ) as rpc:
        current_slot = int(_rpc(rpc, "getSlot", [{"commitment": "confirmed"}]))
        block_time = int(_rpc(rpc, "getBlockTime", [current_slot]))
        assert block_time >= deadline, (
            f"warp to slot {warp_slot} did not advance Clock beyond deadline: "
            f"block_time={block_time}, deadline={deadline}"
        )
        phase2 = _run_client(env, rpc, context, "phase2")

    assert phase2["status"] == 5
    assert phase2["funded"] == "100000000"
    assert phase2["activated"] == "60000000"
    assert phase2["settled"] == "60000000"
    assert phase2["refunded"] == "40000000"
    assert phase2["vault"] == "0"
    assert phase2["recipient"] == "60000000"
    assert phase2["sender"] == "140000000"

    report = {
        "work_item": "FC-SOL-006",
        "environment": "solana-test-validator",
        "agave_version": AGAVE_VERSION,
        "program_id_scope": "ephemeral_local_validator_only",
        "program_id": LOCAL_PROGRAM_ID,
        "sbf_sha256": artifact_sha256,
        "phase1": phase1,
        "warp_slot": warp_slot,
        "phase2": phase2,
        "claims_not_authorized": ["devnet_deployment", "mainnet", "real_value"],
    }
    (tmp_path / "local-validator-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
