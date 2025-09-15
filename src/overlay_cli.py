#!/usr/bin/env python3
"""
Tiny overlay CLI to inspect expansion.

Examples:
  python -m src.overlay_cli --steps '[{"verb":"Summarize","args":{"path":"fixtures/arxiv.atom.xml"}}]'
  python -m src.overlay_cli --overlay research --steps '[{"verb":"Research","args":{"query":"llms"}}]' --enforce-capabilities
"""
import argparse, json, sys
from typing import Any, Dict, List
from .overlays import load_overlays, expand_steps, ExpandOptions

def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--overlay", action="append", default=[], help="Overlay pack to include (e.g., research)")
    ap.add_argument("--no-unknown-verbs", action="store_true", help="Error on unknown verbs")
    ap.add_argument("--enforce-capabilities", action="store_true", help="Block if required capabilities not granted")
    ap.add_argument("--grant", action="append", default=[], help="Grant a capability (e.g., network:fetch)")
    ap.add_argument("--steps", required=True, help='JSON list of steps, e.g. \'[{"verb":"Query","args":{}}]\'')
    args = ap.parse_args(argv)

    overlays = load_overlays(args.overlay)
    steps = json.loads(args.steps)

    canon, lineage, warns = expand_steps(steps, overlays, ExpandOptions(
        overlay_names=args.overlay,
        no_unknown_verbs=args.no_unknown_verbs,
        enforce_capabilities=args.enforce_capabilities,
        granted_capabilities=args.grant
    ))

    out = {
        "canonical": canon,
        "receipts": [r.__dict__ for r in lineage],
        "warnings": warns
    }
    print(json.dumps(out, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
