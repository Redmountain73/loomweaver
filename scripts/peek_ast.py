# scripts/peek_ast.py
# ELI5: show what's inside the generated AST, and what bytecode we'd run.

import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ast_to_vm import compile_module_to_code

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/peek_ast.py <modules_ast.json>")
        sys.exit(2)
    path = sys.argv[1]
    data = json.load(open(path, "r", encoding="utf-8"))
    mods = data.get("modules") or []
    if not mods:
        print("No modules found in AST.")
        sys.exit(1)
    for m in mods:
        code = compile_module_to_code(m)
        print("MODULE:", m.get("name"))
        print("  flow steps:", len(m.get("flow") or []))
        print("  bytecode insns:", len(code))
        if len(code) <= 12:
            # Dump short bytecode to eyeball
            for i, ins in enumerate(code):
                print(f"    {i:02d}: {ins}")
        print()

if __name__ == "__main__":
    main()
