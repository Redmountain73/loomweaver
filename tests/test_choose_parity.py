# tests/test_choose_parity.py
from typing import Any, Dict, List
from src.interpreter import Interpreter

def _mod_with_choose(branches: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "name": "ChooseProbe",
        "astVersion": "2.1.0",
        "inputs": [],
        "flow": [
            {"verb": "Choose", "args": {"branches": branches}}
        ],
    }

def _lit(v: Any) -> Dict[str, Any]:
    if isinstance(v, bool):
        return {"type": "Boolean", "value": v}
    if isinstance(v, (int, float)):
        return {"type": "Number", "value": v}
    if isinstance(v, str):
        return {"type": "String", "value": v}
    return v  # assume already an AST node

def _ret(v: Any) -> Dict[str, Any]:
    return {"verb": "Return", "args": {"expr": _lit(v)}}

def _when(expr_ast: Dict[str, Any], steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"when": expr_ast, "steps": steps}

def _otherwise(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"otherwise": True, "steps": steps}

def _choose_events(interp: Interpreter):
    return [s for s in interp.receipt.get("steps", []) if s.get("event") == "choose"]

def test_choose_when_true_first_branch_selected():
    branches = [
        _when({"type": "Boolean", "value": True},  [_ret(1)]),
        _otherwise([_ret(2)]),
    ]
    m = _mod_with_choose(branches)
    interp = Interpreter()
    result = interp.run(m)

    assert result == 1

    events = _choose_events(interp)
    assert len(events) == 1
    ev = events[0]
    assert ev["predicateTrace"] == [{"expr": "true", "value": True}]
    assert ev["selected"] == {"branch": 0, "kind": "when"}

def test_choose_otherwise_taken_when_no_predicates_true():
    branches = [
        _when({"type": "Boolean", "value": False}, [_ret(1)]),
        _otherwise([_ret(42)]),
    ]
    m = _mod_with_choose(branches)
    interp = Interpreter()
    result = interp.run(m)

    assert result == 42

    events = _choose_events(interp)
    assert len(events) == 2

    first = events[0]
    assert first["predicateTrace"] == [{"expr": "false", "value": False}]
    assert first["selected"] is None

    second = events[1]
    assert second["predicateTrace"] == []
    assert second["selected"] == {"branch": 1, "kind": "otherwise"}

def test_choose_no_branch_matches_and_no_otherwise_returns_none_and_logs_traces():
    branches = [
        _when({"type": "Boolean", "value": False}, [_ret(1)]),
        _when({"type": "Boolean", "value": False}, [_ret(2)]),
    ]
    m = _mod_with_choose(branches)
    interp = Interpreter()
    result = interp.run(m)

    assert result is None

    events = _choose_events(interp)
    assert len(events) == 2
    assert all(ev.get("selected") is None for ev in events)
    assert [ev["predicateTrace"] for ev in events] == [
        [{"expr": "false", "value": False}],
        [{"expr": "false", "value": False}],
    ]
