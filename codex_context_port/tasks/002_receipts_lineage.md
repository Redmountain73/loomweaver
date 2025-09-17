# Task 002 — Receipts Lineage (SPEC-003)

**Goal:** Ensure every step in receipts records overlay lineage, even when overlays are not used.

Steps for Codex:
1. Inspect receipt construction in interpreter/VM.
2. Plumb lineage from the expander into the per-step entries.
3. Add a small test asserting lineage presence and values for Query/Summarize/Report.
