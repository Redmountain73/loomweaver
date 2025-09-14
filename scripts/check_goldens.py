from __future__ import annotations
import json, sys, re
from pathlib import Path

# Ensure project root (which contains `src/`) is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
def parse_semver(s: str):
    m = SEMVER_RE.match(s or "")
    return tuple(int(x) for x in m.groups()) if m else (0,0,0)

def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))

def build_ast_for(path: Path) -> dict:
    from src.tokenizer import tokenize
    from src.parser import parse
    from src.ast_builder import build_ast
    text = path.read_text(encoding="utf-8")
    ast = build_ast(parse(tokenize(text)))
    ast.setdefault("astVersion", "2.0.0")
    return ast

def check_module(path: Path) -> int:
    new_ast = build_ast_for(path)
    golden_path = Path(str(path) + ".json")
    if not golden_path.exists():
        print(f"[ERROR] Missing golden: {golden_path}. Export via: python -m src.loom_cli {path}")
        return 1
    old_ast = json.loads(golden_path.read_text(encoding="utf-8"))
    if canonical(new_ast) == canonical(old_ast):
        print(f"[OK] {path.name} matches golden.")
        return 0
    old_v, new_v = old_ast.get("astVersion","0.0.0"), new_ast.get("astVersion","0.0.0")
    if parse_semver(new_v) <= parse_semver(old_v):
        print(f"[FAIL] AST changed for {path.name} but astVersion did not increase (old {old_v} -> new {new_v}).")
        print(f"       Bump astVersion and update golden via: python -m src.loom_cli {path}")
        return 2
    print(f"[FAIL] AST changed for {path.name} with version bump (old {old_v} -> new {new_v}).")
    print(f"       Update golden: python -m src.loom_cli {path}")
    return 3

def main():
    base = Path("Modules")
    if not base.exists():
        print("[ERROR] Modules/ not found."); sys.exit(1)
    rc = 0
    for p in sorted(base.glob("*.loom")):
        rc |= check_module(p)
    sys.exit(1 if rc else 0)

if __name__ == "__main__":
    main()
