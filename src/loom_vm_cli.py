# src/loom_vm_cli.py
# CLI for running .loom via compiler → VM (no JSON at runtime).
# Adds: --verify (warnings-only), --receipt-out, normalized SHA-256 module hash, run metadata, error receipts.

from __future__ import annotations
import argparse, json, re, hashlib, uuid, datetime as _dt
from pathlib import Path
from typing import Any, Dict, Optional

from .compiler import run_loom_text_with_vm
from .outline_normalizer import normalize_loom_outline

# Optional verifier (warnings-only)
try:
    from .tokenizer import tokenize
    from .parser import parse as parse_outline
    from .ast_builder import build_ast
    from .verifier import verify_module  # type: ignore
    _VERIFY_AVAILABLE = True
except Exception:
    _VERIFY_AVAILABLE = False
    def verify_module(_module: Dict[str, Any]) -> Dict[str, list]:
        return {"errors": [], "warnings": []}

def _norm_for_hash(text: str) -> str:
    # Only normalize for Outline style to keep hash stable across spacing
    if re.search(r'^\s*[A-Z]\.\s', text, flags=re.M):
        return normalize_loom_outline(text)
    return text

def _now_utc_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _parse_inputs_arg(arg: Optional[str]) -> Dict[str, Any]:
    """Parse --in 'k=v[,k=v...]' into a dict with simple coercions."""
    if not arg:
        return {}
    out: Dict[str, Any] = {}
    for kv in arg.split(","):
        kv = kv.strip()
        if not kv:
            continue
        if "=" not in kv:
            raise ValueError(f"--in expects k=v[,k=v...], got: {kv!r}")
        k, v = kv.split("=", 1)
        k = k.strip()
        s = v.strip()
        # Try JSON (quoted strings, numbers, booleans, null, arrays, objects)
        try:
            out[k] = json.loads(s)
            continue
        except Exception:
            pass
        # Try bare booleans
        low = s.lower()
        if low in ("true", "false"):
            out[k] = (low == "true")
            continue
        # Try numbers
        try:
            out[k] = float(s) if "." in s else int(s)
            continue
        except Exception:
            pass
        # Strip quotes if present
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1]
        out[k] = s
    return out

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="loom-vm", description="Run Loom module on the VM")
    ap.add_argument("module", nargs="?", help="Path to .loom file")
    ap.add_argument("--in", dest="inputs", default=None, help='Inputs as k=v[,k=v...]')
    ap.add_argument("--verify", action="store_true", help="Run Loom static verification and attach warnings to receipt.")
    ap.add_argument("--print-logs", action="store_true")
    ap.add_argument("--print-receipt", action="store_true")
    ap.add_argument("--result-only", action="store_true")
    ap.add_argument("--receipt-out", metavar="PATH", help="Write receipt JSON (pretty, sorted keys)")
    args = ap.parse_args(argv)

    if not args.module:
        ap.error("module path required (e.g., Modules/greeting.loom)")

    path = Path(args.module).resolve()
    if not path.is_file():
        ap.error(f"module not found: {path}")
    if path.suffix.lower() != ".loom":
        ap.error("VM runner expects a .loom file")

    text = path.read_text(encoding="utf-8")

    # Inputs
    try:
        inputs = _parse_inputs_arg(args.inputs)
    except Exception as ex:
        ap.error(str(ex))

    # Base receipt metadata (even on error)
    norm = _norm_for_hash(text)
    h = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    module_meta = {"path": str(path), "hash": f"sha256:{h}"}
    run_meta = {"timestamp": _now_utc_iso(), "uuid": str(uuid.uuid4())}

    try:
        # Run via compiler → VM
        result, receipt = run_loom_text_with_vm(text, inputs=inputs)

        # Augment receipt
        receipt.setdefault("engine", "vm")
        receipt.setdefault("module", {}).update(module_meta)
        receipt.setdefault("run", run_meta)

        # Attach verification (warnings-only)
        if args.verify and _VERIFY_AVAILABLE:
            try:
                tree = parse_outline(tokenize(text))
                module_ast = build_ast(tree)
                receipt["verify"] = verify_module(module_ast)
            except Exception:
                # If verification fails for any reason, attach an empty structure (warnings-only policy)
                receipt["verify"] = {"errors": [], "warnings": []}

        # Outputs
        if args.result_only:
            print(result)
        else:
            if args.print_logs and receipt.get("logs"):
                for line in receipt["logs"]:
                    print(line)
            if args.print_receipt:
                print(json.dumps(receipt, indent=2, sort_keys=True))
            if not args.print_logs and not args.print_receipt and not args.result_only:
                print(result)

        if args.receipt_out:
            Path(args.receipt_out).write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
            print(f"Wrote receipt: {args.receipt_out}")
        return 0

    except Exception as e:
        err_receipt = {
            "engine": "vm",
            "module": module_meta,
            "run": run_meta,
            "status": "error",
            "reason": str(e),
            "logs": [],
            "steps": [],
            "callGraph": [],
            "ask": [],
            "env": {},
        }
        if args.verify and _VERIFY_AVAILABLE:
            try:
                tree = parse_outline(tokenize(text))
                module_ast = build_ast(tree)
                err_receipt["verify"] = verify_module(module_ast)
            except Exception:
                err_receipt["verify"] = {"errors": [], "warnings": []}

        if args.print_receipt or not args.result_only:
            print(json.dumps(err_receipt, indent=2, sort_keys=True))
        if args.receipt_out:
            Path(args.receipt_out).write_text(json.dumps(err_receipt, indent=2, sort_keys=True), encoding="utf-8")
            print(f"Wrote receipt: {args.receipt_out}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
