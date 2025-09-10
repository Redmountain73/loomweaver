# scripts/run_module_tests.py
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Make src importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from interpreter import Interpreter  # noqa: E402
from names import normalize_module_slug  # noqa: E402

def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))

def dump_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"

def find_module_ast(mods_doc: dict, name_raw: str) -> Dict[str, Any] | None:
    mods = mods_doc.get("modules") or []
    norm = normalize_module_slug(name_raw or "")
    for m in mods:
        if m.get("name") == name_raw:
            return m
    for m in mods:
        if normalize_module_slug(m.get("name") or "") == norm:
            return m
    return None

def golden_path(module_name: str, test_name: str, golden_dir: Path) -> Path:
    return golden_dir / f"{normalize_module_slug(module_name)}__{normalize_module_slug(test_name)}.receipt.json"

def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run Loom module tests with optional receipt goldens.")
    ap.add_argument("--modules", required=True, help="Modules AST JSON")
    ap.add_argument("--tests", required=True, help="Tests JSON")
    ap.add_argument("--strict", action="store_true", help="Nonzero exit on any failure")
    ap.add_argument("--snapshot", action="store_true", help="Write/update receipt goldens")
    ap.add_argument("--golden-dir", default="agents/loomweaver/goldens", help="Golden receipt directory")
    args = ap.parse_args(argv)

    mods_doc = load_json(Path(args.modules))
    tests_doc = load_json(Path(args.tests))
    tests = tests_doc.get("tests") or tests_doc.get("moduleTests") or []

    golden_dir = Path(args.golden_dir)
    if args.snapshot:
        golden_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    passed = 0
    failures: List[str] = []

    for t in tests:
        total += 1
        module_name = t.get("module") or t.get("name") or "Unnamed Module"
        test_name = t.get("name") or f"test-{total}"
        expected = t.get("expected")
        inputs = dict(t.get("inputs") or {})

        mod_ast = find_module_ast(mods_doc, module_name)
        if not mod_ast:
            msg = f"[FAIL] {module_name} :: {test_name}  (module not found)"
            print(msg)
            failures.append(msg)
            continue

        interp = Interpreter()
        actual = interp.run(mod_ast, inputs=inputs)

        # Value check
        ok_value = (actual == expected)

        # Receipt golden
        gp = golden_path(module_name, test_name, golden_dir)
        receipt_text = dump_json(interp.receipt)
        receipt_ok = True
        if args.snapshot:
            gp.write_text(receipt_text, encoding="utf-8")
            print(f"[SNAPSHOT] wrote {gp}")
        else:
            if gp.exists():
                receipt_ok = (gp.read_text(encoding="utf-8") == receipt_text)
            else:
                # No golden present and not snapshotting → accept value-only test
                receipt_ok = True

        ok = ok_value and receipt_ok
        if ok:
            passed += 1
            print(f"[PASS] {module_name} inputs={inputs} expect={expected} got={actual}")
        else:
            if not ok_value:
                print(f"[FAIL] {module_name} :: {test_name} VALUE expect={expected} got={actual}")
                failures.append(f"value:{module_name}:{test_name}")
            if not receipt_ok:
                print(f"[FAIL] {module_name} :: {test_name} RECEIPT mismatch at {gp}")
                failures.append(f"receipt:{module_name}:{test_name}")

    if failures and args.strict:
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# scripts/run_module_tests.py
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any, Dict, List

# Make the repo root importable, then import from src as a PACKAGE.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.interpreter import Interpreter  # noqa: E402
from src.names import normalize_module_slug  # noqa: E402


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def dump_json(obj: Any) -> str:
    # Deterministic dump for golden diffs
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"


def find_module_ast(mods_doc: dict, name_raw: str) -> Dict[str, Any] | None:
    mods = mods_doc.get("modules") or []
    norm = normalize_module_slug(name_raw or "")
    for m in mods:
        if m.get("name") == name_raw:
            return m
    for m in mods:
        if normalize_module_slug(m.get("name") or "") == norm:
            return m
    return None


def golden_path(module_name: str, test_name: str, golden_dir: Path) -> Path:
    return golden_dir / f"{normalize_module_slug(module_name)}__{normalize_module_slug(test_name)}.receipt.json"


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run Loom module tests with optional receipt goldens.")
    ap.add_argument("--modules", required=True, help="Modules AST JSON")
    ap.add_argument("--tests", required=True, help="Tests JSON")
    ap.add_argument("--strict", action="store_true", help="Nonzero exit on any failure")
    ap.add_argument("--snapshot", action="store_true", help="Write/update receipt goldens")
    ap.add_argument("--golden-dir", default="agents/loomweaver/goldens", help="Golden receipt directory")
    args = ap.parse_args(argv)

    mods_doc = load_json(Path(args.modules))
    tests_doc = load_json(Path(args.tests))
    tests = tests_doc.get("tests") or tests_doc.get("moduleTests") or []

    golden_dir = Path(args.golden_dir)
    if args.snapshot:
        golden_dir.mkdir(parents=True, exist_ok=True)

    failures: List[str] = []
    for i, t in enumerate(tests, start=1):
        module_name = t.get("module") or t.get("name") or "Unnamed Module"
        test_name = t.get("name") or f"test-{i}"
        expected = t.get("expected")
        inputs = dict(t.get("inputs") or {})

        mod_ast = find_module_ast(mods_doc, module_name)
        if not mod_ast:
            msg = f"[FAIL] {module_name} :: {test_name}  (module not found)"
            print(msg)
            failures.append(msg)
            continue

        interp = Interpreter()
        actual = interp.run(mod_ast, inputs=inputs)

        ok_value = (actual == expected)

        # Receipt golden
        gp = golden_path(module_name, test_name, golden_dir)
        receipt_text = dump_json(interp.receipt)
        if args.snapshot:
            gp.write_text(receipt_text, encoding="utf-8")
            print(f"[SNAPSHOT] wrote {gp}")
            receipt_ok = True
        else:
            receipt_ok = (not gp.exists()) or (gp.read_text(encoding="utf-8") == receipt_text)

        ok = ok_value and receipt_ok
        if ok:
            print(f"[PASS] {module_name} inputs={inputs} expect={expected} got={actual}")
        else:
            if not ok_value:
                print(f"[FAIL] {module_name} :: {test_name} VALUE expect={expected} got={actual}")
                failures.append(f"value:{module_name}:{test_name}")
            if not receipt_ok:
                print(f"[FAIL] {module_name} :: {test_name} RECEIPT mismatch at {gp}")
                failures.append(f"receipt:{module_name}:{test_name}")

    return 1 if (failures and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())
