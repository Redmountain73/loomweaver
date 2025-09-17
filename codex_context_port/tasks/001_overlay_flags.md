# Task 001 — Overlay Flags (SPEC-003)

**Goal:** Add overlay flags to the main CLI without breaking baseline.

Steps for Codex:
1. Open `src/loom_cli.py`, `src/compiler.py`.
2. Implement `--overlay`, `--no-unknown-verbs`, `--enforce-capabilities`.
3. Call the compile-time expander (from `src/overlays.py`) before runtime.
4. Update receipts to include overlay lineage fields (`rawVerb`, `mappedVerb`, `overlayDomain`, `overlayVersion`, `capabilityCheck`) without changing the frozen outer schema.
5. Add/adjust tests (focused, non-invasive).
