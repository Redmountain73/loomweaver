from typing import Any, Dict, List, Optional
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.interpreter import Interpreter  # noqa: E402
from src.names import normalize_module_slug  # noqa: E402
from src.fetchers import fixture_fetcher  # noqa: E402


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def canonical_modules_doc(m: dict) -> dict:
    if isinstance(m, dict) and "modules" in m:
        return m
    if isinstance(m, list):
        return {"modules": m}
    return {"modules": []}


def extract_name(m: dict) -> Optional[str]:
    if isinstance(m.get("name"), str):
        return m["name"]
    mod = m.get("module")
    if isinstance(mod, dict) and isinstance(mod.get("name"), str):
        return mod["name"]
    return None


def find_module_ast(mods_doc: dict, name_raw: str) -> Optional[Dict[str, Any]]:
    mods = canonical_modules_doc(mods_doc)["modules"]
    for m in mods:
        if extract_name(m) == name_raw:
            return m
        try:
            if normalize_module_slug(extract_name(m) or "") == normalize_module_slug(name_raw or ""):
                return m
        except Exception:
            pass
    return None


def compare_receipts(actual: dict, golden: dict) -> Optional[str]:
    def sorted_json(obj):
        if isinstance(obj, dict):
            return {k: sorted_json(obj[k]) for k in sorted(obj.keys())}
        if isinstance(obj, list):
            return [sorted_json(x) for x in obj]
        return obj

    a = sorted_json(actual)
    g = sorted_json(golden)

    def walk(pa, pb, path=""):
        if type(pa) != type(pb):
            return path or "<root>"
        if isinstance(pa, dict):
            keys = sorted(set(pa.keys()) | set(pb.keys()))
            for k in keys:
                if k not in pa or k not in pb:
                    return f"{path}.{k}" if path else k
                mismatch = walk(pa[k], pb[k], f"{path}.{k}" if path else k)
                if mismatch:
                    return mismatch
            return None
        if isinstance(pa, list):
            if len(pa) != len(pb):
                return f"{path}.length"
            for i, (xa, xb) in enumerate(zip(pa, pb)):
                mismatch = walk(xa, xb, f"{path}[{i}]")
                if mismatch:
                    return mismatch
            return None
        return None if pa == pb else path or "<root>"

    return walk(a, g, "")


def load_golden_receipt(dir_path: Path, module_slug: str, test_name: str) -> Optional[dict]:
    cand = list(dir_path.glob(f"{module_slug}__{test_name}.receipt.json"))
    if not cand:
        return None
    try:
        with cand[0].open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_golden_receipt(dir_path: Path, module_slug: str, test_name: str, receipt: dict) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / f"{module_slug}__{test_name}.receipt.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modules", required=True)
    ap.add_argument("--tests", required=True)
    ap.add_argument("--golden-dir", required=True)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--snapshot", action="store_true")
    args = ap.parse_args()

    mods_doc = load_json(Path(args.modules))
    tests_doc = load_json(Path(args.tests))
    tests = list(tests_doc.get("tests") or [])

    failures: List[str] = []

    # For determinism: use fixture fetcher for all tests
    def make_interpreter() -> Interpreter:
        return Interpreter(fetcher=fixture_fetcher)

    for i, t in enumerate(tests, start=1):
        module_name = t.get("module") or t.get("name") or "Unnamed Module"
        test_name = t.get("name") or f"test-{i}"
        expected = t.get("expected", t.get("expect"))
        inputs = dict(t.get("inputs") or {})

        # New: allow inline moduleAst in the test; else find by name
        mod_ast = t.get("moduleAst")
        if not mod_ast:
            mod_ast = find_module_ast(mods_doc, module_name)

        if not mod_ast:
            msg = f"[FAIL] {module_name} :: {test_name}  (module not found)"
            print(msg)
            failures.append(msg)
            continue

        interp = make_interpreter()
        actual = interp.run(mod_ast, inputs=inputs)

        ok_value = (actual == expected)

        module_slug = normalize_module_slug(module_name)
        golden_dir = Path(args.golden_dir)
        got_receipt = interp.receipt

        if args.snapshot:
            write_golden_receipt(golden_dir, module_slug, test_name, got_receipt)
            receipt_ok = True
        else:
            golden = load_golden_receipt(golden_dir, module_slug, test_name)
            receipt_ok = (golden is not None) and (compare_receipts(got_receipt, golden) is None)

        if ok_value and receipt_ok:
            print(f"[PASS] {module_name} inputs={inputs} expect={expected} got={actual}")
        else:
            if not ok_value:
                print(f"[FAIL] {module_name} :: {test_name} VALUE expect={expected} got={actual}")
                failures.append(f"value:{module_name}:{test_name}")
            if not receipt_ok:
                where = compare_receipts(got_receipt, golden) if 'golden' in locals() and golden is not None else "no-golden"
                print(f"[FAIL] {module_name} :: {test_name} RECEIPT mismatch at {where}")
                failures.append(f"receipt:{module_name}:{test_name}")

    return 1 if (failures and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
