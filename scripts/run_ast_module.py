# scripts/run_ast_module.py
# ELI5: load AST, lower to VM code, run it, and print code+result.
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ast_to_vm import compile_module_to_code
from vm import VM

_NUM_RE = re.compile(r"^-?\d+(?:\.\d+)?$")

def _coerce_value(s: str):
    # Strip surrounding quotes if present
    if (len(s) >= 2) and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        return s[1:-1]
    # Booleans
    if s.lower() == "true": return True
    if s.lower() == "false": return False
    # Numbers
    if _NUM_RE.match(s):
        return float(s) if "." in s else int(s)
    # Empty string marker "" stays empty after quote stripping above
    return s

def load_modules_ast(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("modules") or []

def pick_module(mods, name):
    for m in mods:
        if m.get("name") == name:
            return m
    raise SystemExit(f"Module not found: {name}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/run_ast_module.py <modules_ast.json> <Module Name> [key=value ...]")
        print('Example: python scripts/run_ast_module.py agents/loomweaver/loomweaver.modules.ast.json "Greeting Module" name=Alice')
        sys.exit(2)

    ast_path = sys.argv[1]
    mod_name = sys.argv[2]
    kvs = sys.argv[3:]
    inputs = {}
    for kv in kvs:
        if "=" in kv:
            k, v = kv.split("=", 1)
            inputs[k] = _coerce_value(v)

    modules = load_modules_ast(ast_path)
    mod = pick_module(modules, mod_name)
    code = compile_module_to_code(mod)

    print(f"Bytecode for '{mod_name}' ({len(code)} insns):")
    for i, ins in enumerate(code):
        if i > 60:
            print("  ..."); break
        print(f"  {i:02d}: {ins}")

    vm = VM(module_name=mod_name)
    result = vm.run(code, inputs=inputs, module_name=mod_name)

    print("RESULT:", result)
    print("ENV:", vm.env)
    print("LOGS:", vm.logs)

if __name__ == "__main__":
    main()
