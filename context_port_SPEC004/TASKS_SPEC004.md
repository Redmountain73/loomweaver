# SPEC-004 — Loomweaver Mentor GPT Agent

---

## Boilerplate Context (Codex, read carefully before coding)

You are working inside **Loomweaver**, the compiler + runtime + toolchain for the Loom language.

- **What Loom is:**  
  Loom is a natural-language-first language. Authors write with friendly verbs (Summarize, Report, Draft, Compare…), and Loomweaver compiles these into a small set of canonical verbs.  

- **What Loomweaver does today (SPEC-003 baseline):**  
  - Deterministically expands author verbs into canonical IR at compile-time.  
  - Loads overlays from JSON (`verbs.core.json`, optional domain packs).  
  - Produces reproducible, auditable receipts (no timestamps, sorted keys).  
  - All receipts now include overlay lineage (`rawVerb`, `mappedVerb`, `overlayDomain`, `overlayVersion`, `capabilityCheck`).  
  - SPEC-003 ensured CLI overlays and receipts are schema-safe and CI-green.  

- **SPEC-004 vision:**  
  Add the **Loomweaver Mentor GPT** — an interactive teaching + feedback agent.  
  Its purpose is to guide authors when writing Loom modules:
  - Detect unknown verbs or suspicious patterns.  
  - Suggest overlay packs (e.g. `research`) when verbs come from them.  
  - Provide inline author guidance (warnings, suggestions) before execution.  
  - Operates at **compile-time only**, preserving deterministic IR and receipts.  

---

## Your Instructions

1. **Placement & Structure**
   - Create a new module: `src/mentor/loomweaver_mentor.py`.  
   - Mentor should expose a `review_module_ast(ast, overlays, flags)` function.  
   - Returns a list of `MentorMessage` dicts:  
     ```json
     {
       "level": "info" | "warn" | "error",
       "message": "string",
       "location": "module/step reference"
     }
     ```

2. **Integration**
   - Wire `loomweaver_mentor` into `scripts/loom.cli.py validate`.  
   - After overlay expansion but before schema validation, run mentor checks.  
   - Show mentor feedback on stdout (sorted, stable order).  
   - Do not block execution unless `--no-unknown-verbs` or `--enforce-capabilities` is set.  

3. **Checks to Implement**
   - **Unknown verbs** → warn by default, error with `--no-unknown-verbs`.  
   - **Overlay suggestions** → if verb exists in known overlay, suggest adding `--overlay <name>`.  
   - **Capability enforcement** → warn vs block, consistent with SPEC-003 flags.  
   - **Style guidance** → warn if module names use forbidden words (`Thing`, `Stuff`, `Whatever`, `Info`, `Data`).  

4. **Receipts**
   - Add `mentorFeedback` field at the *top level* of receipts.  
   - Each entry is a `MentorMessage` dict.  
   - Preserve all existing fields (do not break schema).  

5. **Tests**
   - New test file: `tests/mentor_test.py`.  
   - Cases:
     - Unknown verb triggers warning.  
     - Overlay suggestion appears for missing overlay.  
     - Capability violation blocked with `--enforce-capabilities`.  
     - Forbidden names flagged.  
     - `mentorFeedback` appears in receipts deterministically.  

6. **Work until CI is green**
   - `python scripts/loom.cli.py validate --strict` must pass.  
   - `python scripts/loom.cli.py test --strict` must pass.  
   - `pytest -q` must pass.  
   - If mismatches appear, refresh goldens with:  
     ```bash
     python scripts/loom.cli.py test --strict --update-goldens
     ```

7. **Branch + PR**
   - Commit work on `feat/spec004-mentor`.  
   - Push branch to origin.  
   - Open PR titled:  
     ```
     SPEC-004: Loomweaver Mentor GPT (author guidance + inline checks)
     ```  
   - PR body: summarize changes, list new tests, confirm CI green.  

---

## After Completion

When the task is complete, also provide **recommendations** on:  
- What further mentor rules should be added (style, safety, pedagogy).  
- How to expose the mentor as a **VS Code extension** or **browser GPT agent** in future specs.  
