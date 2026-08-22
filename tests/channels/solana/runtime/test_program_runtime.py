from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[4]
MANIFEST = ROOT / "programs" / "foundry-channel-vault" / "program" / "Cargo.toml"
PROGRAM_SOURCE = MANIFEST.parent / "src" / "lib.rs"


def test_executable_channel_vault_program_host_suite() -> None:
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo is required for the FC-SOL-006 runtime suite")

    completed = subprocess.run(
        [cargo, "test", "--manifest-path", str(MANIFEST)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr


def test_first_runtime_slice_is_executable_but_does_not_claim_deployment() -> None:
    source = PROGRAM_SOURCE.read_text(encoding="utf-8")
    cargo = MANIFEST.read_text(encoding="utf-8")

    assert 'crate-type = ["cdylib", "lib"]' in cargo
    assert "entrypoint!(process_instruction);" in source
    for handler in (
        "process_activate_voucher",
        "process_bind_recipient",
        "process_request_close",
    ):
        assert f"fn {handler}" in source

    assert "declare_id!" not in source
    assert "spl-token" not in cargo
    assert "spl-associated-token-account" not in cargo
