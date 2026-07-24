from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_local_proof_is_executable_from_a_clean_checkout() -> None:
    completed = subprocess.run(
        [sys.executable, "examples/local_proof.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result["response_lost_after_commit"] is True
    assert result["recovery_outcome"] == "confirmed"
    assert result["may_rematerialize"] is False
    assert result["replay_blocked"] is True
    assert result["economic_effect_count"] == 1
