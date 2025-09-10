import json
from pathlib import Path

from src.loom_cli import main as loom_interpreter_main
from src.loom_vm_cli import main as loom_vm_main


def _read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def test_interpreter_verify_attaches_section(tmp_path: Path):
    mod = Path("Modules") / "greeting.loom"
    out = tmp_path / "interp_receipt.json"
    rc = loom_interpreter_main([
        str(mod),
        "--verify",
        "--in", 'name="Alice"',
        "--print-receipt",
        "--receipt-out", str(out),
    ])
    assert rc == 0
    j = _read_json(out)
    assert "verify" in j
    assert isinstance(j["verify"], dict)
    assert "errors" in j["verify"] and "warnings" in j["verify"]
    # Warnings-only policy: presence of the section must not cause non-zero exit
    assert j.get("status", "ok") != "error"


def test_vm_verify_attaches_section(tmp_path: Path):
    mod = Path("Modules") / "greeting.loom"
    out = tmp_path / "vm_receipt.json"
    rc = loom_vm_main([
        str(mod),
        "--verify",
        "--in", 'name="Alice"',
        "--print-receipt",
        "--receipt-out", str(out),
    ])
    assert rc == 0
    j = _read_json(out)
    assert "verify" in j
    assert isinstance(j["verify"], dict)
    assert "errors" in j["verify"] and "warnings" in j["verify"]
    # Ensure standard receipt fields still there
    assert j["module"]["path"].endswith(str(mod))
    assert j["module"]["hash"].startswith("sha256:")
