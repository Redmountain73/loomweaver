#!/usr/bin/env python3
"""
Overlay CLI (SPEC-003)

Implements:
  --overlay <name>              e.g. --overlay research
  --no-unknown-verbs            error on verbs without any mapping
  --enforce-capabilities        enforce capability checks instead of warn
  --grant <cap>                 grant specific capability, e.g. --grant network:fetch
  --in <json file>              input steps JSON (list of {"verb","args"})
  --out <json file>             output canonical+receipts JSON
  --pretty                      pretty-print JSON

This keeps overlays compile-time only and stamps receipt lineage:
  rawVerb, mappedVerb, overlayDomain, overlayVersion, capabilityCheck
"""
from __future__ import annotations
import argparse, json, os, sys
from typing import Any, Dict, List

from .overlays import load_overlays, expand_steps, ExpandOptions

def _read_steps(path: str) -> List[Dict[str, Any]]:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of steps [{verb, args}].")
    return data

def _write_json(path: str | None, obj: Dict[str, Any], pretty: bool) -> None:
    dump = json.dumps(obj, indent=2 if pretty else None)
    if path:
        with open(path, "w", encoding="utf-8") as w:
            w.write(dump + ("\n" if pretty else ""))
    else:
        print(dump)

def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="overlay-cli")
    ap.add_argument("--overlay", action="append", default=[], help="Overlay pack to include (e.g., research)")
    ap.add_argument("--no-unknown-verbs", action="store_true", help="Error on unknown verbs")
    ap.add_argument("--enforce-capabilities", action="store_true", help="Block if capabilities missing")
    ap.add_argument("--grant", action="append", default=[], help="Grant a capability (may repeat)")
    ap.add_argument("--in", dest="infile", required=True, help="Input steps JSON file")
    ap.add_argument("--out", dest="outfile", help="Output JSON file (optional)")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print output JSON")
    args = ap.parse_args(argv)

    overlays = load_overlays(args.overlay)
    steps = _read_steps(args.infile)

    canon, lineage, warns = expand_steps(
        steps, overlays,
        ExpandOptions(
            overlay_names=args.overlay,
            no_unknown_verbs=args.no_unknown_verbs,
            enforce_capabilities=args.enforce_capabilities,
            granted_capabilities=args.grant,
        )
    )

    out = {
        "canonical": canon,
        "receipts": [l.__dict__ for l in lineage],
        "warnings": warns,
        "overlaysLoaded": ["core"] + list(args.overlay),
    }
    _write_json(args.outfile, out, args.pretty)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
