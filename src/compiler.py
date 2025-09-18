# src/compiler.py
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .tokenizer import tokenize
from .parser import parse
from .ast_builder import build_ast
from .interpreter import Interpreter, RuntimeErrorLoom
from .overlays import load_overlays, ExpandOptions, expand_modules_doc, expand_module_ast
from .vm import TypeErrorLoom


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile Loom outline to modules AST")
    parser.add_argument("input", help="Outline source file (.loom/.md)")
    parser.add_argument("output", help="Output AST JSON path")
    parser.add_argument("--overlay", action="append", default=[], help="Overlay pack to include (repeatable)")
    parser.add_argument("--no-unknown-verbs", action="store_true", help="Error on verbs without overlay mapping")
    parser.add_argument("--enforce-capabilities", action="store_true", help="Block missing overlay capabilities")

    args = parser.parse_args(argv or sys.argv[1:])

    in_path = Path(args.input)
    out_path = Path(args.output)

    if not in_path.exists():
        print(f"compiler: input not found: {in_path}")
        return 2

    text = in_path.read_text(encoding="utf-8")
    tokens = tokenize(text)
    parsed = parse(tokens)
    ast = build_ast(parsed)

    modules_doc = ast if (isinstance(ast, dict) and "modules" in ast) else {"modules": [ast]}

    overlays = load_overlays(args.overlay)
    expand_opts = ExpandOptions(
        overlay_names=list(args.overlay or []),
        no_unknown_verbs=bool(args.no_unknown_verbs),
        enforce_capabilities=bool(args.enforce_capabilities),
    )
    modules_doc, overlay_warns = expand_modules_doc(modules_doc, overlays, expand_opts)
    for warn in overlay_warns:
        print(f"compiler: overlay warning: {warn}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(modules_doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"compiler: wrote {out_path}")
    return 0


def run_loom_text_with_vm(
    text: str,
    inputs: Optional[Dict[str, Any]] = None,
    *,
    overlay_names: Optional[List[str]] = None,
    no_unknown_verbs: bool = False,
    enforce_capabilities: bool = False,
    **_,
) -> Tuple[Any, Dict[str, Any]]:
    """Compatibility helper used by tests and vm_shim."""

    module_path_obj: Optional[Path] = None
    source_text = text
    if isinstance(text, str) and "\n" not in text and "\r" not in text:
        path_candidate = Path(text)
        if path_candidate.exists():
            module_path_obj = path_candidate
            source_text = path_candidate.read_text(encoding="utf-8")

    tokens = tokenize(source_text)
    parsed = parse(tokens)
    module_ast = build_ast(parsed)

    overlays = load_overlays(overlay_names or [])
    expand_opts = ExpandOptions(
        overlay_names=list(overlay_names or []),
        no_unknown_verbs=bool(no_unknown_verbs),
        enforce_capabilities=bool(enforce_capabilities),
    )
    expanded_module, overlay_warns = expand_module_ast(module_ast, overlays, expand_opts)

    interpreter = Interpreter(enforce_capabilities=enforce_capabilities)
    try:
        result = interpreter.run(copy.deepcopy(expanded_module), inputs=inputs)
    except RuntimeErrorLoom as exc:
        raise TypeErrorLoom(str(exc)) from exc

    receipt = copy.deepcopy(interpreter.receipt)
    receipt["engine"] = "vm"
    loaded_names = ["core"] + [name for name in expand_opts.overlay_names if name and name != "core"]
    seen = set()
    overlays_loaded = []
    for name in loaded_names:
        if name in seen:
            continue
        seen.add(name)
        overlays_loaded.append(name)
    receipt["overlaysLoaded"] = overlays_loaded
    if overlay_warns:
        logs = receipt.setdefault("logs", [])
        for warn in overlay_warns:
            logs.append({"level": "warning", "event": "overlay", "message": warn})

    digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    if module_path_obj is not None:
        module_info = receipt.setdefault("module", {})
        if isinstance(module_info, dict):
            module_info.setdefault("name", module_path_obj.name)
            module_info["path"] = str(module_path_obj)
            module_info["hash"] = f"sha256:{digest}"
            module_info.setdefault("astVersion", "2.1.0")
    else:
        module_info = receipt.setdefault("module", {})
        if isinstance(module_info, dict) and "hash" not in module_info:
            module_info["hash"] = f"sha256:{digest}"

    return result, receipt


if __name__ == "__main__":
    raise SystemExit(main())
