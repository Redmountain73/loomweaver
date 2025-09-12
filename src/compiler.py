# src/compiler.py
from __future__ import annotations
import json
import sys
from pathlib import Path

# Run as a module: python -m src.compiler <outline.md> <out.ast.json>

from .tokenizer import tokenize
from .parser import parse
from .ast_builder import build_ast


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print("usage: python -m src.compiler <outline.md> <out.ast.json>")
        return 2

    in_path = Path(argv[0])
    out_path = Path(argv[1])

    if not in_path.exists():
        print(f"compiler: input not found: {in_path}")
        return 2

    text = in_path.read_text(encoding="utf-8")
    tokens = tokenize(text)
    parsed = parse(tokens)
    ast = build_ast(parsed)

    # Ensure top-level bundle: {"modules":[...]}
    modules_doc = ast if (isinstance(ast, dict) and "modules" in ast) else {"modules": [ast]}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(modules_doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"compiler: wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
