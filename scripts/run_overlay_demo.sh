#!/usr/bin/env bash
set -euo pipefail

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
IN="$ROOT/samples/overlay_sample.steps.json"
OUT="$ROOT/overlay_demo.out.json"

python -m src.overlay_cli \
  --in "$IN" \
  --pretty \
  --out "$OUT"

echo "Wrote: $OUT"
echo "-----"
sed -n '1,120p' "$OUT"

echo
echo "[research overlay + enforced + grant]"
python -m src.overlay_cli \
  --overlay research \
  --enforce-capabilities \
  --grant network:fetch \
  --in "$IN" \
  --pretty
