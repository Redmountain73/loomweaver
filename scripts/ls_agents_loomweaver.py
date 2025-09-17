#!/usr/bin/env python3
"""
Emit a JSON inventory of agents/loomweaver (safe with spaces in paths).

Usage examples (run from repo root):
  python "scripts/ls_agents_loomweaver.py" --pretty
  python "scripts/ls_agents_loomweaver.py" --root "agents/loomweaver" > agents_loomweaver_tree.json
"""

from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from typing import Dict, Any, List

EXCLUDES_DIR = {".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".DS_Store"}
EXCLUDES_FILE = {".DS_Store"}

def sha1_first_mb(path: str) -> str:
    h = hashlib.sha1()
    try:
        with open(path, "rb") as r:
            h.update(r.read(1024 * 1024))  # hash first 1MB for speed
        return h.hexdigest()[:10]
    except Exception:
        return "0000000000"

def walk_tree(root: str) -> Dict[str, Any]:
    root_abs = os.path.abspath(root)
    entries: List[Dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(root_abs):
        # prune excluded dirs (stable sort)
        dirnames[:] = sorted([d for d in dirnames if d not in EXCLUDES_DIR])
        rel_dir = os.path.relpath(dirpath, root_abs)
        rel_dir = "" if rel_dir == "." else rel_dir

        # record directory entry (skip root itself to keep JSON tidy)
        if rel_dir:
            d_path = rel_dir.replace("\\", "/")
            st = os.stat(os.path.join(root_abs, rel_dir))
            entries.append({
                "type": "dir",
                "path": d_path,
                "mtime": int(st.st_mtime)
            })

        # files
        for f in sorted(filenames):
            if f in EXCLUDES_FILE:
                continue
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, root_abs).replace("\\", "/")
            try:
                st = os.stat(full)
                size = st.st_size
                mtime = int(st.st_mtime)
            except Exception:
                size, mtime = -1, 0
            entries.append({
                "type": "file",
                "path": rel,
                "size": size,
                "sha1_1mb": sha1_first_mb(full),
                "mtime": mtime,
            })

    # stable sort: dirs before files at same depth, then lexicographically
    def sort_key(e):
        depth = e["path"].count("/") if e["path"] else 0
        return (e["type"] != "dir", depth, e["path"])
    entries.sort(key=sort_key)

    return {
        "root": root_abs.replace("\\", "/"),
        "generated_at": int(time.time()),
        "entries": entries
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="agents/loomweaver", help="Folder to inventory")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        print(json.dumps({
            "error": f"root not found: {args.root}"
        }), file=sys.stderr)
        return 2

    data = walk_tree(args.root)
    print(json.dumps(data, indent=2 if args.pretty else None, sort_keys=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
