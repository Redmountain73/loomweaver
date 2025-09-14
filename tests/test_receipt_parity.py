from pathlib import Path
from typing import Dict, Any

from src.interpreter import run_module_from_file
from src.compiler import run_loom_text_with_vm


def _normalize_receipt(r: Dict[str, Any]) -> Dict[str, Any]:
    """Drop volatile fields and keep only comparable parts for loose parity."""
    r = dict(r or {})
    r.pop("run", None)
    r.pop("module", None)
    keep = {}
    for k in ("engine", "logs", "env", "callGraph", "steps"):
        if k in r:
            keep[k] = r[k]
    return keep


def _assert_loose_parity(mod_path: Path, inputs: Dict[str, Any]):
    # Interpreter path
    result_i, receipt_i = run_module_from_file(str(mod_path), inputs=inputs)

    # VM path
    text = mod_path.read_text(encoding="utf-8")
    result_v, receipt_v = run_loom_text_with_vm(text, inputs=inputs)

    # Results must match
    assert result_i == result_v

    Ri = _normalize_receipt(receipt_i)
    Rv = _normalize_receipt(receipt_v)

    # logs should match exactly for these modules (usually empty)
    assert Ri.get("logs", []) == Rv.get("logs", [])

    # callGraph should match (no calls in these modules)
    assert Ri.get("callGraph", []) == Rv.get("callGraph", [])

    # env: compare overlapping keys only
    env_i = Ri.get("env", {}) or {}
    env_v = Rv.get("env", {}) or {}
    common = set(env_i.keys()) & set(env_v.keys())
    for k in common:
        assert env_i[k] == env_v[k]


def test_parity_greeting():
    """Interpreter vs VM parity for Greeting."""
    mod_path = Path("Modules") / "greeting.loom"
    assert mod_path.exists(), "Expected Modules/greeting.loom to exist"
    _assert_loose_parity(mod_path, {"name": "Alice"})


def test_parity_factorial():
    """Interpreter vs VM parity for Factorial (after Show-blank guard)."""
    mod_path = Path("Modules") / "factorial.loom"
    assert mod_path.exists(), "Expected Modules/factorial.loom to exist"
    _assert_loose_parity(mod_path, {"n": 6})
