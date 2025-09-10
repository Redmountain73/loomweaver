# scripts/loom.cli.py
import argparse, sys, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents" / "loomweaver"

def run_py(args_list):
    return subprocess.run([sys.executable] + args_list, cwd=ROOT).returncode

def main():
    ap = argparse.ArgumentParser(prog="loom")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_validate = sub.add_parser("validate", help="validate program+modules+caps JSON")
    p_validate.add_argument("--strict", action="store_true", help="nonzero exit on schema/logic errors")
    p_validate.add_argument("--warnings-as-errors", action="store_true", help="escalate warnings to nonzero exit")
    p_validate.set_defaults(cmd="validate")

    p_test = sub.add_parser("test", help="run loomweaver tests via VM")
    p_test.add_argument("--strict", action="store_true", help="nonzero exit on failures")
    p_test.set_defaults(cmd="test")

    p_run = sub.add_parser("run", help="run a module via VM")
    p_run.add_argument("module")
    p_run.add_argument("--enforce-capabilities", action="store_true")
    p_run.add_argument("kv", nargs="*")
    p_run.set_defaults(cmd="run")

    p_compile = sub.add_parser("compile", help="compile loomweaver outline -> modules AST")
    p_compile.set_defaults(cmd="compile")

    args = ap.parse_args()

    if args.cmd == "validate":
        return run_py([
            str(ROOT / "scripts" / "validate_program.py"),
            "--program", str(AGENTS / "loomweaver.program.json"),
            "--modules", str(AGENTS / "loomweaver.modules.ast.json"),
            "--capabilities", str(AGENTS / "loomweaver.capabilities.json"),
            *(["--strict"] if args.strict else []),
            *(["--warnings-as-errors"] if getattr(args, "warnings_as_errors", False) else []),
        ])
    if args.cmd == "test":
        return run_py([
            str(ROOT / "scripts" / "run_module_tests.py"),
            "--modules", str(AGENTS / "loomweaver.modules.ast.json"),
            "--tests",   str(AGENTS / "loomweaver.tests.json"),
            *(["--strict"] if args.strict else []),
        ])
    if args.cmd == "run":
        return run_py([
            str(ROOT / "scripts" / "run_ast_module.py"),
            str(AGENTS / "loomweaver.modules.ast.json"),
            args.module, *args.kv
        ])
    if args.cmd == "compile":
        return run_py([
            str(ROOT / "src" / "compiler.py"),
            str(AGENTS / "loomweaver.outline.md"),
            str(AGENTS / "loomweaver.modules.ast.json")
        ])

if __name__ == "__main__":
    raise SystemExit(main())
