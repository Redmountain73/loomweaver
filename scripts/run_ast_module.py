# scripts/run_ast_module.py
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.interpreter import Interpreter  # noqa: E402
from src.names import normalize_module_slug  # noqa: E402


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser(description="Run a module from an AST bundle.")
    ap.add_argument("modules_ast", help="Path to agents/...modules.ast.json")
    ap.add_argument("module_name", help="Module to run (raw or normalized)")
    ap.add_argument("kv", nargs="*", help="inputs as k=v")
    ap.add_argument("--enforce-capabilities", action="store_true", help="deny on policy violations")
    args = ap.parse_args()

    moddoc = load_json(Path(args.modules_ast))
    mods = moddoc.get("modules") or []
    # Find by raw or normalized
    target = None
    for m in mods:
        if m.get("name") == args.module_name:
            target = m; break
    if not target:
        norm = normalize_module_slug(args.module_name)
        for m in mods:
            if normalize_module_slug(m.get("name") or "") == norm:
                target = m; break
    if not target:
        print(f"Module '{args.module_name}' not found.")
        raise SystemExit(2)

    # Parse k=v pairs
    inputs = {}
    for pair in args.kv:
        if "=" in pair:
            k, v = pair.split("=", 1)
            inputs[k] = v

    interp = Interpreter(enforce_capabilities=bool(args.enforce_capabilities))
    result = interp.run(target, inputs=inputs)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
