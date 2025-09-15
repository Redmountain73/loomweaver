#!/usr/bin/env python3
"""
Loom VM CLI (compat) — emits structured error receipts if VM engine is not wired.

This CLI preserves the public interface documented in the README:

Usage:
  python -m src.loom_vm_cli ./Modules/vm_choose_repeat_call.loom \
    --in key=value [--in key=value ...] \
    --print-logs --print-receipt --result-only --receipt-out ./vm_receipt.json

Behavior:
- Delegates to src.vm_shim.run_loom_text_with_vm (compat layer).
- On success: prints logs/result per flags and writes a valid receipt.
- On failure: emits a structured **error receipt** matching the frozen schema.
"""

from __future__ import annotations
import argparse, json, os, sys, time, uuid
from typing import Any, Dict, List, Tuple

# Import the shim instead of compiler to avoid modifying existing runtime files
from .vm_shim import run_loom_text_with_vm

def parse_kv_pairs(pairs: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for item in pairs:
        if "=" not in item:
            raise ValueError(f"--in expects key=value, got: {item!r}")
        k, v = item.split("=", 1)
        out[k] = v
    return out

def make_base_receipt(engine: str, module_name: str) -> Dict[str, Any]:
    # Minimal valid skeleton matching your frozen schema (outer shape only)
    return {
        "engine": engine,
        "module": {
            "name": module_name,
            "astVersion": "2.1.0",          # keep in sync with repo default
            "hash": "sha256(normalizedSource)"  # placeholder until wired
        },
        "run": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "uuid": str(uuid.uuid4()),
        },
        "logs": [],
        "steps": [],
        "callGraph": [],
        "ask": [],
        "env": {},
        # status/reason added on error
    }

def write_receipt(path: str | None, receipt: Dict[str, Any], print_receipt: bool) -> None:
    dump = json.dumps(receipt, indent=2)
    if print_receipt:
        print(dump)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(dump + "\n")

def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="loom_vm_cli")
    ap.add_argument("module_path", help="Path to a .loom module file")
    ap.add_argument("--in", dest="inputs", action="append", default=[], help="Input key=value (repeatable)")
    ap.add_argument("--print-logs", action="store_true", help="Print runtime logs to stdout")
    ap.add_argument("--print-receipt", action="store_true", help="Print receipt JSON to stdout")
    ap.add_argument("--result-only", action="store_true", help="Print only the result to stdout")
    ap.add_argument("--receipt-out", help="Write receipt JSON to this file")
    args = ap.parse_args(argv)

    engine = "vm"
    module_path = args.module_path
    module_name = os.path.basename(module_path)
    inputs = parse_kv_pairs(args.inputs or [])

    base = make_base_receipt(engine, module_name)

    try:
        result, receipt, logs = run_loom_text_with_vm(
            module_path,
            inputs,
            print_logs=args.print_logs,
            print_receipt=args.print_receipt,
            receipt_out=args.receipt_out,
            result_only=args.result_only,
        )

        # Ensure required fields exist in the successful receipt
        receipt.setdefault("engine", engine)
        receipt.setdefault("module", base["module"])
        receipt.setdefault("run", base["run"])
        receipt.setdefault("logs", logs or [])
        receipt.setdefault("steps", receipt.get("steps", []))
        receipt.setdefault("callGraph", receipt.get("callGraph", []))
        receipt.setdefault("ask", receipt.get("ask", []))
        receipt.setdefault("env", receipt.get("env", {}))

        # Print per flags
        if args.print_logs and logs:
            for line in logs:
                print(line)
        if args.result_only:
            # Print the result only
            if isinstance(result, (str, int, float, bool)):
                print(result)
            else:
                print(json.dumps(result))
        write_receipt(args.receipt_out, receipt, args.print_receipt)
        return 0

    except Exception as e:
        # Structured error receipt
        base["status"] = "error"
        base["reason"] = str(e)
        # For visibility in CLI usage:
        if args.print_logs:
            print(f"[vm] error: {e}", file=sys.stderr)
        write_receipt(args.receipt_out, base, args.print_receipt)
        # Non-zero exit to indicate failure to callers
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
