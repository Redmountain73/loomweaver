#!/usr/bin/env bash
# SPEC-003 repo reconciliation: normalize overlays, fixtures, scripts, and prototypes.
set -euo pipefail

# Resolve repo root relative to this script (works with spaces)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "Repo root: $ROOT"

# 1) Ensure directories exist
mkdir -p "$ROOT/agents/loomweaver/overlays"
mkdir -p "$ROOT/fixtures"
mkdir -p "$ROOT/prototypes/ts/src" || true

# 2) Delete stray extensionless overlay file
if [[ -f "$ROOT/agents/loomweaver/overlays/verbs.core" ]]; then
  echo "Removing stray: agents/loomweaver/overlays/verbs.core"
  rm -f "$ROOT/agents/loomweaver/overlays/verbs.core"
  git rm -f --cached "agents/loomweaver/overlays/verbs.core" 2>/dev/null || true
fi

# 3) Write overlay packs (full replacements)
cat > "$ROOT/agents/loomweaver/overlays/verbs.core.json" <<'JSON'
{
  "overlay": "core",
  "version": "0.1.0",
  "verbs": {
    "Query": {
      "mappedVerb": "Call",
      "notes": "Used to fetch from a module or resource."
    },
    "Summarize": {
      "mappedVerb": "Call",
      "op": "xml.firstTitle",
      "defaultInto": "summary",
      "notes": "Summarize by extracting first <title> from XML (fixture-backed)."
    },
    "Report": {
      "mappedVerb": ["Make", "Show"],
      "pipeline": [
        { "Make": { "op": "format.compose" } },
        { "Show": { "sink": "stdout" } }
      ],
      "notes": "Report = format then show on stdout."
    },
    "Explain": {
      "mappedVerb": "Show",
      "sink": "stdout",
      "notes": "Explain = show text to stdout."
    },
    "Check": {
      "mappedVerb": "Choose",
      "notes": "Check = branch/conditional."
    }
  }
}
JSON

cat > "$ROOT/agents/loomweaver/overlays/verbs.research.json" <<'JSON'
{
  "overlay": "research",
  "version": "0.1.0",
  "verbs": {
    "Research": {
      "mappedVerb": "Call",
      "capabilities": ["network:fetch"],
      "notes": "Perform a research fetch (fixture-backed in tests)."
    },
    "Review": {
      "mappedVerb": "Show",
      "sink": "stdout",
      "notes": "Display retrieved material."
    },
    "Compare": {
      "mappedVerb": "Choose",
      "notes": "Compare → branch logic."
    },
    "Cite": {
      "mappedVerb": "Make",
      "op": "format.citation",
      "notes": "Format citation text."
    },
    "Draft": {
      "mappedVerb": "Make",
      "op": "text.compose",
      "notes": "Create a draft text."
    },
    "Revise": {
      "mappedVerb": "Make",
      "op": "text.rewrite",
      "notes": "Revise a draft text."
    },
    "Narrate": {
      "mappedVerb": "Call",
      "op": "audio.tts",
      "capabilities": ["audio:tts"],
      "notes": "Convert text to speech (requires capability)."
    },
    "Illustrate": {
      "mappedVerb": "Call",
      "op": "image.gen",
      "capabilities": ["image:gen"],
      "notes": "Generate an illustration (requires capability)."
    }
  }
}
JSON

# 4) Add SPEC-003 fixture (full replacement)
cat > "$ROOT/fixtures/arxiv.atom.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>arXiv Recent</title>
  <entry>
    <title>Quantum Kittens and the Lattice of Meows</title>
    <id>http://arxiv.org/abs/0000.00001</id>
  </entry>
  <entry>
    <title>Graph Transformers for Small, Cute Data</title>
    <id>http://arxiv.org/abs/0000.00002</id>
  </entry>
</feed>
XML

# 5) Remove redundant JS helper (Python version replaces it)
if [[ -f "$ROOT/scripts/show-project-roots.js" ]]; then
  echo "Removing redundant scripts/show-project-roots.js"
  rm -f "$ROOT/scripts/show-project-roots.js"
  git rm -f --cached "scripts/show-project-roots.js" 2>/dev/null || true
fi

# 6) Move reference-only TS prototypes out of src/ (if present; untracked is fine)
for d in cli overlay validator; do
  if [[ -d "$ROOT/src/$d" ]]; then
    echo "Relocating TS prototype: src/$d -> prototypes/ts/src/$d"
    mkdir -p "$ROOT/prototypes/ts/src"
    mv -f "$ROOT/src/$d" "$ROOT/prototypes/ts/src/"
  fi
done

# 6a) Add a tiny README for prototypes (if not present)
if [[ ! -f "$ROOT/prototypes/ts/README.md" ]]; then
  cat > "$ROOT/prototypes/ts/README.md" <<'MD'
These TypeScript files are reference-only prototypes for SPEC-003 (CLI flags, overlay loader, validator).
They are **not** part of the Python runtime. Keep them here to avoid confusion with production code under ./src.
MD
fi

# 7) Ensure helper scripts are executable
chmod +x "$ROOT/scripts/gen_file_tree.py" 2>/dev/null || true
chmod +x "$ROOT/scripts/show_project_roots.py" 2>/dev/null || true
chmod +x "$ROOT/scripts/ls_agents_loomweaver.py" 2>/dev/null || true

# 8) Stage and commit the changes (add only the touched files)
git add \
  "$ROOT/agents/loomweaver/overlays/verbs.core.json" \
  "$ROOT/agents/loomweaver/overlays/verbs.research.json" \
  "$ROOT/fixtures/arxiv.atom.xml" \
  "$ROOT/prototypes/ts/README.md" 2>/dev/null || true

# Also stage moved directories if they now exist
if [[ -d "$ROOT/prototypes/ts/src" ]]; then
  git add "$ROOT/prototypes/ts/src" 2>/dev/null || true
fi

git commit -m "SPEC-003: normalize overlays, add fixture, remove redundant JS, relocate TS prototypes" || true

# 9) Quick verification
python "$ROOT/scripts/ls_agents_loomweaver.py" --pretty | sed -n '1,120p'
echo "✅ SPEC-003 reconcile complete."
