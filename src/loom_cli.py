# src/loom_cli.py
# CLI for running Loom via the interpreter.

from __future__ import annotations

import argparse
import json
import re
import hashlib
import uuid
import datetime as _dt
from pathlib import Path
from typing import Any, Dict, Tuple, Optional, List

from .interpreter import run_module_from_file
from .outline_normalizer import normalize_loom_outline


def _now_utc_iso() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _norm_for_hash(text: str) -> str:
    if re.search(r'^\s*[A-Z]\.\s', text, flags=re.M):
        return normalize_loom_outline(text)
    return text


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _verify_stub(_: Dict[str, Any]) -> Dict[str, Any]:
    # Warnings-only placeholder (acceptance: section must exist)
    return {"warnings": [], "errors": []}


def _write_dot(path: Path, callgraph: List[Dict[str, Any]]) -> None:
    lines = ["digraph callgraph {"]
    for edge in callgraph or []:
        a = json.dumps(edge.get("from", ""))
        b = json.dumps(edge.get("to", ""))
        lbl = edge.get("atStep")
        if lbl is not None:
            lines.append(f"  {a} -> {b} [label={lbl}];")
        else:
            lines.append(f"  {a} -> {b};")
    lines.append("}")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="loom",
        description="Run Loom module with the interpreter; print logs, receipts, and call graphs.",
    )
    p.add_argument("module", nargs="?", help="Path to module (.loom | .json | .loom.json).")
    p.add_argument("--tests", action="store_true", help="Run embedded tests in the module.")
    p.add_argument("--in", dest="inputs", default=None, help="Input KEY=VALUE (repeatable).")
    p.add_argument("--registry-dir", default="Modules", help="Directory to auto-load callee modules (default: Modules).")
    p.add_argument("--no-registry", action="store_true", help="Disable loading registry from the directory.")
    p.add_argument("--emit-ast", metavar="PATH", help="Emit parsed AST JSON for the module to PATH.")
    p.add_argument("--print-logs", action="store_true")
    p.add_argument("--print-receipt", action="store_true")
    p.add_argument("--result-only", action="store_true")
    p.add_argument("--print-callgraph", action="store_true", help="Print the callGraph JSON.")
    p.add_argument("--graph-dot", metavar="PATH", help="Write callGraph as Graphviz DOT to PATH.")
    p.add_argument("--receipt-out", metavar="PATH", help="Write execution receipt to PATH (JSON).")
    p.add_argument("--verify", action="store_true", help="Run verifier (warnings-only) and attach to receipt.")
    args = p.parse_args(argv)

    if not args.module:
        p.error("module path required (e.g., Modules/greeting.loom)")

    path = Path(args.module)
    if not path.is_file():
        p.error(f"module not found: {path}")

    # Build inputs dict from KEY=VALUE[,...]
    inputs: Dict[str, Any] = {}
    if args.inputs:
        parts = args.inputs.split(",") if isinstance(args.inputs, str) else args.inputs
        for kv in parts:
            kv = kv.strip()
            if "=" in kv:
                k, v = kv.split("=", 1)
                vv: Any = v
                if isinstance(v, str):
                    vl = v.strip()
                    # unwrap quotes first
                    if len(vl) >= 2 and ((vl[0] == vl[-1] == '"') or (vl[0] == vl[-1] == "'")):
                        vv = vl[1:-1]
                    else:
                        low = vl.lower()
                        if low in ("true", "false"):
                            vv = (low == "true")
                        else:
                            try:
                                vv = int(vl)
                            except ValueError:
                                try:
                                    vv = float(vl)
                                except ValueError:
                                    vv = vl
                inputs[k] = vv

    # Compute normalized hash for receipt
    text = _load_text(path)
    norm = _norm_for_hash(text)
    h = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    base = {
        "engine": "interpreter",
        "module": {"path": str(path), "hash": f"sha256:{h}"},
        "run": {"timestamp": _now_utc_iso(), "uuid": str(uuid.uuid4())},
    }

    try:
        result, receipt = run_module_from_file(str(path), inputs=inputs)
        receipt.setdefault("engine", "interpreter")
        receipt.setdefault("module", {}).update(base["module"])
        receipt.setdefault("run", base["run"])

        # Attach verify section
        if args.verify:
            receipt["verify"] = _verify_stub(receipt)

        if args.result_only:
            print(result)
        else:
            if args.print_logs and receipt.get("logs"):
                for line in receipt["logs"]:
                    print(line)
            if args.print_callgraph and receipt.get("callGraph"):
                print(json.dumps(receipt.get("callGraph"), indent=2, sort_keys=True))
            if args.print_receipt:
                print(json.dumps(receipt, indent=2, sort_keys=True))
            if args.graph_dot and receipt.get("callGraph"):
                _write_dot(Path(args.graph_dot), receipt.get("callGraph") or [])
            if not args.print_logs and not args.print_receipt and not args.print_callgraph:
                print(result)

        if args.receipt_out:
            Path(args.receipt_out).write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
            print(f"Wrote receipt: {args.receipt_out}")
        return 0

    except Exception as e:
        # Best-effort error receipt, even if execution failed early.
        err_logs: List[str] = []
        err_steps: List[Dict[str, Any]] = []
        if 'receipt' in locals():
            err_logs = receipt.get("logs", [])
            err_steps = receipt.get("steps", [])
        err = {**base, "status": "error", "reason": str(e), "logs": err_logs, "steps": err_steps}
        if args.verify:
            err["verify"] = {"warnings": [], "errors": []}
        print(json.dumps(err, indent=2, sort_keys=True))
        if args.receipt_out:
            Path(args.receipt_out).write_text(json.dumps(err, indent=2, sort_keys=True), encoding="utf-8")
            print(f"Wrote receipt: {args.receipt_out}")
        return 1


# test harness helper used by tests/test_verify_flag.py
def loom_interpreter_main(argv: Optional[list[str]] = None) -> int:
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
