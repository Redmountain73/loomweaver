from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.interpreter import Interpreter  # noqa: E402
from src.names import normalize_module_slug  # noqa: E402

def load_json(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)

def find_module(mods_doc: dict, name_raw: str):
    mods = (mods_doc.get("modules") or [])
    for m in mods:
        core = m.get("module") if isinstance(m.get("module"), dict) else m
        if core.get("name") == name_raw:
            return m
        try:
            if normalize_module_slug(core.get("name") or "") == normalize_module_slug(name_raw or ""):
                return m
        except Exception:
            pass
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modules", default=str(ROOT / "agents" / "loomweaver" / "loomweaver.modules.ast.json"))
    ap.add_argument("--module", required=True, help="module name (raw)")
    ap.add_argument("--enforce-capabilities", action="store_true")
    ap.add_argument("kv", nargs="*", help="inputs as name=value")
    args = ap.parse_args()

    mods_doc = load_json(Path(args.modules))
    mod = find_module(mods_doc, args.module)
    if not mod:
        print(f"Module not found: {args.module}", file=sys.stderr)
        return 1

    inputs = {}
    for pair in args.kv:
        if "=" in pair:
            k, v = pair.split("=", 1)
            inputs[k] = v

    interp = Interpreter(enforce_capabilities=bool(args.enforce_capabilities))
    result = interp.run(mod, inputs=inputs)
    if result is not None:
        print(result)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
