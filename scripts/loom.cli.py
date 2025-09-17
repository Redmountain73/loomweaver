#!/usr/bin/env python3
# // Codex smoke test – no logic changed
"""
Loom CLI (friendly wrapper)

Subcommands:
  validate  -> scripts/validate_program.py (canonical AST + program)
  test      -> scripts/run_module_tests.py (strict by default)
  run       -> scripts/run_ast_module.py (one module, pass inputs)
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PROGRAM    = ROOT / "agents" / "loomweaver" / "loomweaver.program.json"
DEFAULT_MODULES    = ROOT / "agents" / "loomweaver" / "loomweaver.modules.ast.json"
DEFAULT_CAPS       = ROOT / "agents" / "loomweaver" / "loomweaver.capabilities.json"  # <— renamed
DEFAULT_TESTS      = ROOT / "agents" / "loomweaver" / "loomweaver.tests.json"
DEFAULT_GOLDENS    = ROOT / "agents" / "loomweaver" / "goldens"

def run(cmd: list[str]) -> int:
    print("+", " ".join(str(c) for c in cmd))
    return subprocess.call(cmd)

def cmd_validate(args: argparse.Namespace) -> int:
    validate_py = ROOT / "scripts" / "validate_program.py"
    cmd = [
        sys.executable, str(validate_py),
        "--program", str(DEFAULT_PROGRAM),
        "--modules", str(DEFAULT_MODULES),
        "--capabilities", str(DEFAULT_CAPS),
    ]
    if args.strict:
        cmd.append("--strict")
    return run(cmd)

def cmd_test(args: argparse.Namespace) -> int:
    tests_py = ROOT / "scripts" / "run_module_tests.py"
    cmd = [
        sys.executable, str(tests_py),
        "--modules", str(DEFAULT_MODULES),
        "--tests",   str(DEFAULT_TESTS),
        "--golden-dir", str(DEFAULT_GOLDENS),
    ]
    if args.strict:
        cmd.append("--strict")
    if args.snapshot:
        cmd.append("--snapshot")
    return run(cmd)

def cmd_run(args: argparse.Namespace) -> int:
    run_py = ROOT / "scripts" / "run_ast_module.py"
    cmd = [
        sys.executable, str(run_py),
        "--modules", str(DEFAULT_MODULES),
        "--module", args.module,
    ]
    if args.enforce_capabilities:
        cmd.append("--enforce-capabilities")
    cmd.extend(args.kv or [])
    return run(cmd)

def main() -> int:
    ap = argparse.ArgumentParser(prog="loom", description="Loom CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_val = sub.add_parser("validate", help="validate canonical AST + program + caps")
    ap_val.add_argument("--strict", action="store_true")
    ap_val.set_defaults(func=cmd_validate)

    ap_test = sub.add_parser("test", help="run loomweaver module tests")
    ap_test.add_argument("--strict", action="store_true", help="fail on any mismatch")
    ap_test.add_argument("--snapshot", action="store_true", help="(re)write golden receipts")
    ap_test.set_defaults(func=cmd_test)

    ap_run = sub.add_parser("run", help="run a single module with inputs")
    ap_run.add_argument("--module", required=True, help="module name (raw)")
    ap_run.add_argument("--enforce-capabilities", action="store_true")
    ap_run.add_argument("kv", nargs="*", help="inputs as name=value")
    ap_run.set_defaults(func=cmd_run)

    args = ap.parse_args()
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
