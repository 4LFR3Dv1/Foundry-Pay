from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


RUNTIME_DIR = Path(__file__).parent


def test_real_solana_test_validator_lifecycle() -> None:
    if os.name == "nt":
        pytest.skip("FC-SOL-006 solana-test-validator target is Linux/WSL")
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        and os.environ.get("FC_SOL_006_RUN_VALIDATOR") != "1"
    ):
        pytest.skip("set FC_SOL_006_RUN_VALIDATOR=1 to run the real validator suite")

    completed = subprocess.run(
        ["bash", str(RUNTIME_DIR / "run-local-validator.sh")],
        cwd=RUNTIME_DIR,
        check=False,
        capture_output=True,
        text=True,
        timeout=1_200,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
    receipts = [
        json.loads(line)
        for line in completed.stdout.splitlines()
        if line.startswith("{") and '"ok":true' in line
    ]
    assert receipts, completed.stdout
    receipt = receipts[-1]
    assert receipt["agaveVersion"] == "v2.1.21"
    assert receipt["programIdScope"] == "ephemeral_local_validator_only"
    assert receipt["phase1"]["bindRecipient"] <= 1_232
    assert receipt["phase2"]["status"] == 5
    assert receipt["phase2"]["funded"] == "100000000"
    assert receipt["phase2"]["activated"] == "60000000"
    assert receipt["phase2"]["settled"] == "60000000"
    assert receipt["phase2"]["refunded"] == "40000000"
    assert receipt["phase2"]["vault"] == "0"
    assert receipt["phase2"]["recipient"] == "60000000"
    assert receipt["phase2"]["sender"] == "140000000"
