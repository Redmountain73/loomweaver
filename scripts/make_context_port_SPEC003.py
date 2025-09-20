#!/usr/bin/env python3
"""
Generate SPEC-003 context port zip for Loomweaver.
This bundles history, vision, team, and roadmap into one reproducible artifact.
"""

import os, zipfile, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PORT_DIR = os.path.join(ROOT, "context_port_SPEC003")
ZIP_PATH = os.path.join(ROOT, "context_port_SPEC003.zip")

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content.strip() + "\n")

now = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())

# === CONTENTS ===

README = f"""# Loomweaver Context Port — SPEC-003 Baseline

Generated: {now}

This archive captures Loomweaver’s state after SPEC-003 (overlay flags + receipts lineage), with CI green.
Use it to seed new sessions with Nova + Codex, ensuring no context drift.

## How to use
- Share `context_port_SPEC003.zip` when opening a new chat.
- Inside are: history, vision, team roles, and roadmap.
- Codex can read `README_SPEC003.md` for exact task scope.
"""

HISTORY = """# Project History (Up to SPEC-003)

- **Loom vision:** Natural-language-first programming language for writing intelligent agents.
- **Loomweaver role:** Compiler + runtime + toolchain that expands Loom text into canonical IR and produces receipts.
- **SPEC-001:** Cross-module calls & receipts. Call verb, deterministic receipts, CI goldens locked.
- **SPEC-002:** External calls + sandbox. Fixture-based fetch, arXiv demo, sandbox-safe.
- **SPEC-003:** Overlays. Added compile-time overlay expansion, lineage in receipts, and CLI flags:
  - `--overlay`
  - `--no-unknown-verbs`
  - `--enforce-capabilities`
- **CI milestone:** SPEC-003 merged with all tests green (py3.11 + py3.13).

Receipts are now canonical + lineage-rich, overlays are schema-safe, and tests reproducibly validate.
"""

VISION = """# Vision & Philosophy

Loom is designed to let humans express programs in plain natural language,
while Loomweaver guarantees determinism, safety, and auditability.

- **Authors write:** `Summarize`, `Report`, `Draft`, `Compare`…
- **Compiler expands:** To canonical verbs (`Make`, `Show`, `Call`, `Ask`, `Choose`, `Repeat`, `Return`).
- **Receipts:** Every run leaves a transparent, deterministic receipt.
- **Overlays:** Extend vocabulary safely; always compile-time only, never at runtime.

Goal: AI-native programming language that is flexible for humans, strict for machines.
"""

TEAM = """# Team Loom

- **You (Founder/Architect):** Set direction, approve merges, maintain vision.
- **Nova (Mentor):** Compass + guide; keeps philosophy intact, explains design tradeoffs.
- **SA (Software Architect GPT):** Executes specs, drafts reference code, ensures CI green.
- **Codex (IDE Pairing GPT):** Hands-on coding partner in VS Code/GitHub; implements tasks, debugs until green.

## Norms
- Work on feature branches; keep main green.
- Always validate + test before merge.
- Receipts remain the single source of truth.
"""

ROADMAP = """# Roadmap — Beyond SPEC-003

- **SPEC-004: Loomweaver Mentor**
  - Author guidance overlays.
  - Inline feedback + explainability.
  - Richer teaching/authoring aids.

- **Future packs**
  - Finance, robotics, media ops.
  - Capability-gated, fixture-backed.

- **Monetization**
  - Long-term: Loom language + Loomweaver toolchain + derivative agents.

Core invariant: Determinism, reproducibility, and auditability never sacrificed.
"""

def main():
    write(os.path.join(PORT_DIR, "README_SPEC003.md"), README)
    write(os.path.join(PORT_DIR, "HISTORY.md"), HISTORY)
    write(os.path.join(PORT_DIR, "VISION.md"), VISION)
    write(os.path.join(PORT_DIR, "TEAM_LOOM.md"), TEAM)
    write(os.path.join(PORT_DIR, "ROADMAP.md"), ROADMAP)

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(PORT_DIR):
            for fn in files:
                fp = os.path.join(root, fn)
                arc = os.path.relpath(fp, ROOT)
                z.write(fp, arcname=arc)

    print(f"Wrote: {PORT_DIR}")
    print(f"Zipped: {ZIP_PATH}")

if __name__ == "__main__":
    main()
