#!/usr/bin/env bash
# Meta-CLI for Loom that safely routes to overlay or VM tools.
# Works with paths that include spaces.

set -euo pipefail

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

usage() {
  cat <<'HLP'
Loom meta-CLI

USAGE
  scripts/loom.sh overlays --in <steps.json> [--overlay <name>] [--no-unknown-verbs] [--enforce-capabilities] [--grant <cap>] [--out <file>] [--pretty]
  scripts/loom.sh vm <module.loom> [--in key=value ...] [--print-logs] [--print-receipt] [--result-only] [--receipt-out file]

MODES
  overlays   Run SPEC-003 overlay expansion end-to-end via src.overlay_cli (compile-time only).
  vm         Run the VM CLI (currently shimmed to emit a structured error receipt until VM wiring lands).

EXAMPLES
  # Overlay compile on sample steps:
  scripts/loom.sh overlays --in "samples/overlay_sample.steps.json" --pretty

  # Overlay compile with research pack, enforce capabilities:
  scripts/loom.sh overlays --overlay research --enforce-capabilities --grant network:fetch \
    --in "samples/overlay_sample.steps.json" --pretty

  # VM run (will produce a structured error receipt until VM wiring is complete):
  scripts/loom.sh vm "./Modules/vm_choose_repeat_call.loom" \
    --in who=guest --print-logs --print-receipt --receipt-out ./vm_receipt.json
HLP
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

mode="$1"; shift

case "$mode" in
  overlays)
    # Pass-through to overlay CLI
    python -m src.overlay_cli "$@"
    ;;
  vm)
    if [[ $# -lt 1 ]]; then
      echo "vm mode requires a module path (.loom)" >&2
      usage
      exit 2
    fi
    python -m src.loom_vm_cli "$@"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "unknown mode: $mode" >&2
    usage
    exit 2
    ;;
esac
