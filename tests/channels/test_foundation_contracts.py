"""Executable checks for the Foundry Channels foundation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).parents[2]


def load_checker() -> ModuleType:
    path = ROOT / "scripts" / "check_channel_foundation.py"
    spec = importlib.util.spec_from_file_location("check_channel_foundation", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_foundation_contracts_and_gates_pass() -> None:
    result = load_checker().validate()

    assert result["status"] == "passed", result["errors"]
    assert result["checks"]["schemas"]["count"] == 7
    assert result["checks"]["negative_vectors"]["count"] >= 12
    assert result["checks"]["closing_race_vector"]["valid"] is True
    assert result["checks"]["work_graph"]["ready_items"] == [
        "FC-PROTO-005",
        "FC-PROTO-006",
        "FC-VAL-003",
    ]
    assert result["checks"]["work_graph"]["ready_with_incomplete_dependencies"] == {}
    assert result["checks"]["accounting"] == {
        "conservation": True,
        "rights_bounds": True,
    }
