# scripts/generate_tree.py
# ELI5: walk the repo and write a pretty tree to a file in UTF-8.
# Avoids Windows console encoding issues by NOT printing box-drawing to stdout.

from __future__ import annotations
import os
import sys
from typing import List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

EXCLUDE_DIRS = {".venv", ".pytest_cache", "__pycache__", ".git"}
EXCLUDE_FILES = {".DS_Store"}
EXCLUDE_SUFFIXES = {".pyc"}

STYLE_UNICODE = {
    "branch": "├── ",
    "last":   "└── ",
    "pipe":   "│   ",
    "space":  "    ",
}
STYLE_ASCII = {
    "branch": "|-- ",
    "last":   "`-- ",
    "pipe":   "|   ",
    "space":  "    ",
}

def should_exclude_dir(name: str) -> bool:
    return name in EXCLUDE_DIRS or name.startswith(".git")

def should_exclude_file(name: str) -> bool:
    if name in EXCLUDE_FILES: return True
    return any(name.endswith(suf) for suf in EXCLUDE_SUFFIXES)

def build_tree_lines(root: str, style: dict) -> List[str]:
    lines: List[str] = []
    lines.append(".")
    def walk(dir_path: str, prefix: str):
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return
        # Split into dirs/files with filters
        dirs = [d for d in entries if os.path.isdir(os.path.join(dir_path, d)) and not should_exclude_dir(d)]
        files = [f for f in entries if os.path.isfile(os.path.join(dir_path, f)) and not should_exclude_file(f)]

        # Dirs
        for idx, d in enumerate(dirs):
            is_last = (idx == len(dirs) - 1) and (len(files) == 0)
            connector = style["last"] if is_last else style["branch"]
            lines.append(f"{prefix}{connector}{d}/")
            # Next prefix propagation
            next_prefix = prefix + (style["space"] if is_last else style["pipe"])
            walk(os.path.join(dir_path, d), next_prefix)

        # Files
        for idx, f in enumerate(files):
            is_last = (idx == len(files) - 1)
            connector = style["last"] if is_last else style["branch"]
            lines.append(f"{prefix}{connector}{f}")

    walk(root, "")
    return lines

def main(argv: list[str]) -> int:
    # Usage: python scripts/generate_tree.py [out_path] [--style=unicode|ascii]
    out_path = "loom_tree.txt"
    style = STYLE_UNICODE
    for a in argv[1:]:
        if a.startswith("--style="):
            v = a.split("=", 1)[1].strip().lower()
            style = STYLE_ASCII if v == "ascii" else STYLE_UNICODE
        else:
            out_path = a

    lines = build_tree_lines(ROOT, style)
    # Always write UTF-8 to file; don't stream to stdout to dodge Windows codepages
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {out_path} ({len(lines)} lines)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
