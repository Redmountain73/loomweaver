#!/usr/bin/env python3
"""
Create codex_context_port/ and zip it as codex_context_port.zip.
Safe for paths with spaces. Deterministic content.
"""
from __future__ import annotations
import os, zipfile, time

ROOT = r"/workspaces/Loom vs code files"
PORT_DIR = os.path.join(ROOT, "codex_context_port")
ZIP_PATH = os.path.join(ROOT, "codex_context_port.zip")

def write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content.strip() + "\n")

now = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())

README_CODEX = f"""# Codex Context Port for Loom/Loomweaver

Generated: {now}

## Vision
Pair OpenAI **Codex** with this repo inside VS Code so natural language tasks become auditable branches and PRs. Codex reads/edit files you open, runs commands you approve, and can move work between local and cloud.

## What’s inside
- `TEAM_LOOM_CODEX.md` — roles and working norms
- `SPEC-CODEX-000.md` — install, sign-in, GitHub linking, usage patterns
- `tasks/001_overlay_flags.md` — SPEC-003 tasks for overlay flags
- `tasks/002_receipts_lineage.md` — SPEC-003 receipts enrichment tasks
- `scripts/setup_github_remote.sh` — safe remote add/push

## Quickstart
1. Install the Codex IDE extension in VS Code and sign in with ChatGPT (see SPEC-CODEX-000).
2. Connect your GitHub account when prompted.
3. Open this repo, create a feature branch, and run the tasks in `tasks/`.
"""

TEAM = """# Team Loom — Codex Roles

- **You (Architect/Founder)** — sets direction, approves merges.
- **Nova (Mentor)** — keeps philosophy and invariants aligned.
- **SA (Software Architect GPT)** — executes specs, writes patches, fixes CI.
- **Codex** — hands-on coding partner inside VS Code: reads open files, proposes edits, runs commands with your consent, and prepares diffs.

## Working norms
- One small task at a time; branch + PR per task.
- Keep SPEC-002 green; SPEC-003 lands behind flags.
- Always review Codex diffs; receipts remain source of truth.
"""

SPEC = f"""# SPEC-CODEX-000 — IDE Pairing (Codex in VS Code)

## Background
We want AI-native pairing for SPEC-003 overlays without destabilizing SPEC-002.

## Requirements
- Install Codex IDE extension in VS Code.
- Sign in with ChatGPT; no manual API keys.
- Link GitHub for repo ops (branches/PRs).
- Keep actions auditable via branches and commits.

## Install & Sign In (VS Code)
1) **Install the extension**
   - Use the official VSIX via VS Code: **Command Palette → “Extensions: Install from VSIX…”** and select the file.
2) **Sign in with ChatGPT**
   - Use the extension’s sign-in flow; it opens your browser to ChatGPT. Approve access.
3) **Connect GitHub**
   - When prompted, link your GitHub account so Codex can manage branches/PRs.

## Usage patterns (repo with spaces in path)
- Open the repo folder. Select files you want Codex to read.
- Ask Codex in the IDE panel to perform scoped tasks: “Add --overlay flags to loom_cli”, “Write overlay_core_test.py”.
- Approve edits; inspect diffs; commit to a feature branch.

## Guardrails
- Always run tests locally (e.g., `pytest -q -k overlay_core_test`) before merging.
- Require PR review on `main`.
"""

TASKS1 = """# Task 001 — Overlay Flags (SPEC-003)

**Goal:** Add overlay flags to the main CLI without breaking baseline.

Steps for Codex:
1. Open `src/loom_cli.py`, `src/compiler.py`.
2. Implement `--overlay`, `--no-unknown-verbs`, `--enforce-capabilities`.
3. Call the compile-time expander (from `src/overlays.py`) before runtime.
4. Update receipts to include overlay lineage fields (`rawVerb`, `mappedVerb`, `overlayDomain`, `overlayVersion`, `capabilityCheck`) without changing the frozen outer schema.
5. Add/adjust tests (focused, non-invasive).
"""

TASKS2 = """# Task 002 — Receipts Lineage (SPEC-003)

**Goal:** Ensure every step in receipts records overlay lineage, even when overlays are not used.

Steps for Codex:
1. Inspect receipt construction in interpreter/VM.
2. Plumb lineage from the expander into the per-step entries.
3. Add a small test asserting lineage presence and values for Query/Summarize/Report.
"""

SETUP_GH = """#!/usr/bin/env bash
# Idempotent GitHub remote setup. Safe with spaces in path.
set -euo pipefail
ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT/.."

if git rev-parse --git-dir >/dev/null 2>&1; then
  echo "Git repo detected."
else
  echo "Initializing git repo..."
  git init
  git add .
  git commit -m "init"
fi

if git remote get-url origin >/dev/null 2>&1; then
  echo "Remote 'origin' already set: $(git remote get-url origin)"
else
  echo "No 'origin' remote. To set it:"
  echo "  git remote add origin https://github.com/<your-username>/<your-repo>.git"
  echo "  git branch -M main"
  echo "  git push -u origin main"
fi
"""

def main():
    # write docs
    write(os.path.join(PORT_DIR, "README_CODEX.md"), README_CODEX)
    write(os.path.join(PORT_DIR, "TEAM_LOOM_CODEX.md"), TEAM)
    write(os.path.join(PORT_DIR, "SPEC-CODEX-000.md"), SPEC)
    write(os.path.join(PORT_DIR, "tasks", "001_overlay_flags.md"), TASKS1)
    write(os.path.join(PORT_DIR, "tasks", "002_receipts_lineage.md"), TASKS2)
    # script
    os.makedirs(os.path.join(PORT_DIR, "scripts"), exist_ok=True)
    sp = os.path.join(PORT_DIR, "scripts", "setup_github_remote.sh")
    with open(sp, "w", encoding="utf-8", newline="\n") as f:
        f.write(SETUP_GH.strip() + "\n")
    os.chmod(sp, 0o755)

    # zip it
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(PORT_DIR):
            for fn in files:
                fp = os.path.join(root, fn)
                arc = os.path.relpath(fp, ROOT)
                z.write(fp, arcname=arc)

    print(f"Wrote: {PORT_DIR}")
    print(f"Zipped: {ZIP_PATH}")

if __name__ == "__main__":
    main()
