#!/usr/bin/env python3
"""
VM compatibility shim for loom_vm_cli.

Purpose:
- Provide the expected symbol `run_loom_text_with_vm` without modifying `compiler.py`.
- In this stage, it raises a controlled RuntimeError so the CLI can emit a structured error receipt.
- In the next step, we will replace this shim to call the real VM pipeline.
"""

from __future__ import annotations
from typing import Any, Dict, Tuple

def run_loom_text_with_vm(
    module_path: str,
    inputs: Dict[str, Any] | None = None,
    *,
    print_logs: bool = False,
    print_receipt: bool = False,
    receipt_out: str | None = None,
    result_only: bool = False,
) -> Tuple[Any, Dict[str, Any], list[str]]:
    """
    Expected interface for the VM CLI.

    Returns:
        (result, receipt, logs)

    In this shim build, we raise a controlled error so the CLI can emit a structured error receipt.
    """
    raise RuntimeError(
        "VM engine not wired in this SPEC-003 shim build. "
        "Use the overlay CLI for now: `python -m src.overlay_cli --in samples/overlay_sample.steps.json --pretty`."
    )
