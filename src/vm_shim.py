#!/usr/bin/env python3
"""
VM compatibility shim for loom_vm_cli.

Goal:
- Provide the expected symbol `run_loom_text_with_vm`.
- Try hard to delegate to *any* existing real runner in the repo:
  1) src.compiler.run_loom_text_with_vm
  2) src.vm.run_loom_text_with_vm
  3) src.vm.run_module_from_file / src.compiler.run_module_from_file / src.interpreter.run_module_from_file
  4) Fallback subprocess to `python -m src.loom_cli` (if present)
- If delegation is impossible, raise a clear RuntimeError. The CLI catches it and emits a structured error receipt.

We keep this shim isolated so SPEC-002 remains untouched. When SPEC-003 wiring is complete,
we can either delete this file or turn it into a thin alias.
"""

from __future__ import annotations
import importlib
import json
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Tuple

Result = Tuple[Any, Dict[str, Any], List[str]]

def _try_call(func, module_path: str, inputs: Dict[str, Any], **flags) -> Result:
    """Normalize call contract across possible runners."""
    # Popular shapes we normalize to (result, receipt, logs)
    out = func(module_path, inputs, **flags)
    # Heuristics: many runners return either (result, receipt, logs) or just receipt
    if isinstance(out, tuple) and len(out) == 3:
        return out  # as-is
    if isinstance(out, tuple) and len(out) == 2:
        result, receipt = out
        return result, receipt, []
    if isinstance(out, dict):
        # assume 'receipt-like' object only
        return None, out, []
    # Unknown shape — wrap it into a receipt-ish envelope
    return out, {"engine": "vm", "logs": [], "steps": [], "callGraph": [], "ask": [], "env": {}}, []

def _maybe(module_name: str):
    try:
        return importlib.import_module(module_name)
    except Exception:
        return None

def run_loom_text_with_vm(
    module_path: str,
    inputs: Dict[str, Any] | None = None,
    *,
    print_logs: bool = False,
    print_receipt: bool = False,
    receipt_out: str | None = None,
    result_only: bool = False,
) -> Result:
    """
    Expected interface for the VM CLI.

    Returns:
        (result, receipt, logs)
    """
    inputs = inputs or {}

    # 1) Try src.compiler.run_loom_text_with_vm
    compiler = _maybe("src.compiler")
    if compiler and hasattr(compiler, "run_loom_text_with_vm"):
        return _try_call(
            getattr(compiler, "run_loom_text_with_vm"),
            module_path, inputs,
            print_logs=print_logs,
            print_receipt=print_receipt,
            receipt_out=receipt_out,
            result_only=result_only,
        )

    # 2) Try src.vm.run_loom_text_with_vm (if a vm module exists)
    vm_mod = _maybe("src.vm")
    if vm_mod and hasattr(vm_mod, "run_loom_text_with_vm"):
        return _try_call(
            getattr(vm_mod, "run_loom_text_with_vm"),
            module_path, inputs,
            print_logs=print_logs,
            print_receipt=print_receipt,
            receipt_out=receipt_out,
            result_only=result_only,
        )

    # 3) Try "run_module_from_file" on common modules (compiler, vm, interpreter)
    for mod_name in ("src.compiler", "src.vm", "src.interpreter"):
        mod = _maybe(mod_name)
        if mod and hasattr(mod, "run_module_from_file"):
            return _try_call(
                getattr(mod, "run_module_from_file"),
                module_path, inputs,
                print_logs=print_logs,
                print_receipt=print_receipt,
                receipt_out=receipt_out,
                result_only=result_only,
            )

    # 4) Subprocess fallback to `python -m src.loom_cli` if present
    #    We only ask it to emit a receipt; we parse and return it.
    loom_cli = _maybe("src.loom_cli")
    if loom_cli is not None:
        try:
            with tempfile.TemporaryDirectory() as td:
                tmp_receipt = os.path.join(td, "receipt.json")
                # Try to run with a minimal flag set that many CLIs support.
                # We pass inputs as --in key=value pairs.
                in_args: List[str] = []
                for k, v in (inputs or {}).items():
                    in_args.extend(["--in", f"{k}={v}"])
                cmd = [
                    sys.executable, "-m", "src.loom_cli", module_path,
                    "--print-receipt", "--receipt-out", tmp_receipt, "--result-only"
                ] + in_args
                proc = subprocess.run(cmd, capture_output=True, text=True)
                # Best effort: if it wrote a receipt, use it; otherwise surface stderr as logs.
                logs: List[str] = []
                if proc.stdout.strip():
                    logs.append(proc.stdout.strip())
                if proc.stderr.strip():
                    logs.append(proc.stderr.strip())
                if os.path.isfile(tmp_receipt):
                    with open(tmp_receipt, "r", encoding="utf-8") as f:
                        receipt = json.load(f)
                    # We do not know the result; set None and return logs we captured.
                    return None, receipt, logs
                # If we got here, subprocess did not produce a receipt — include outputs in the error.
        except Exception as e:
            # Ignore and fall through to the final error.
            pass

    # Nothing worked — inform the caller (CLI will emit a structured error receipt)
    tried = [
        "src.compiler.run_loom_text_with_vm",
        "src.vm.run_loom_text_with_vm",
        "src.(compiler|vm|interpreter).run_module_from_file",
        "python -m src.loom_cli (subprocess fallback)"
    ]
    raise RuntimeError(
        "VM engine not wired (or no known entrypoint found). Tried: "
        + ", ".join(tried)
        + ". If you want overlay-only expansion, use: "
        + "`python -m src.overlay_cli --in samples/overlay_sample.steps.json --pretty`."
    )
