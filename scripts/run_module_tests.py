# scripts/run_module_tests.py
# Run tests from agents/<agent>.tests.json against modules AST via VM.

import argparse, json, os, sys
from pathlib import Path

# allow importing from src
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ast_to_vm import compile_module_to_code
from vm import VM

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modules", required=True, help="path to agents/<agent>.modules.ast.json")
    ap.add_argument("--tests", required=True, help="path to agents/<agent>.tests.json")
    ap.add_argument("--strict", action="store_true", help="nonzero exit on any failure")
    args = ap.parse_args()

    modules_ast = load_json(Path(args.modules))
    tests = load_json(Path(args.tests)).get("tests") or []

    by_name = {m.get("name"): m for m in modules_ast.get("modules") or []}
    failures = 0

    for t in tests:
        mod = by_name.get(t.get("module"))
        if not mod:
            print(f"[FAIL] module not found: {t.get('module')}")
            failures += 1
            continue
        code = compile_module_to_code(mod)
        vm = VM(module_name=mod.get("name"))
        res = vm.run(code, inputs=t.get("inputs") or {}, module_name=mod.get("name"))
        ok = (res == t.get("expect"))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {mod.get('name')} inputs={t.get('inputs')} expect={t.get('expect')} got={res}")
        if not ok:
            failures += 1

    if args.strict and failures:
        sys.exit(1)

if __name__ == "__main__":
    main()
