# Loom — Natural Outline Programming Language

**Loom** is a natural outline programming language: **executable, modular, reflexive**. It’s the **post‑Python, post‑JSON substrate** where humans and machines share the same language.

## Vision
- A single outline that is readable by people **and** executable by machines.
- Deterministic by construction: **normalize → canonicalize → hash** over normalized source.
- **Auditable by default** via first‑class receipts capturing provenance, predicate traces, selections, call graphs, and run metadata.
- Composable at every scale: Atoms (actions) → Organs (modules) → Organisms (agents) → Rhizomes (networks) → Ecosystem.
- Operationally pragmatic: **VM‑first** runtime with interpreter parity for tests and validation.

## Purpose
- **Unify code, data, and intent** in outline form—no spec/exec drift.
- **Reproducible runs** with stable identity (hash of normalized source).
- **Strong semantics**: boolean‑only truthiness; defined operator precedence.
- **Tooling that proves what happened**: receipts, call graphs, predicate traces.

## Not a JSON Skin (or sugary DSL)
- JSON/YAML are interchange formats; Loom’s outline is the **source of truth** and identity.
- Small, orthogonal verbs (Make, Show, Ask, Return, Choose, Repeat, Call, **NEG**) with strict semantics.
- Runtime + receipts + tooling are first‑class parts of the language, not afterthoughts.

## Ontology & Intelligence Layer
- **Atoms** (actions) → **Organs** (modules) → **Organisms** (agents) → **Rhizomes** (networks) → **Ecosystem** (interconnected).
- **LoomWeaver**: the intelligence layer (instructioneer, validator, mentor).

## Locked Invariants (do not break)
- **Runtime:** VM‑first execution; interpreter retained for parity/tests.
- **Normalization:** outline text (2/4/6 indent) → canonical → **hash over normalized source only**.
- **Parser:** clause promotion for `when/else if/otherwise`; Repeat header fuse/split.
- **Semantics:** operator precedence `not > and > or > comparisons > arithmetic`; **strict boolean‑only truthiness**.
- **Schema:** Choose + Call hardened.
- **Interpreter:** receipts include `inputsResolved` (with provenance), `predicateTrace`, `selected`.
- **VM:** supports `Make, Show, Ask, Return, Choose (with predicate receipts), Repeat (asc/desc inclusive), Call, NEG`.
- **Receipts schema (frozen):**

```json
{
  "engine": "vm" | "interpreter",
  "module": { "name": "string", "astVersion": "2.1.0", "hash": "sha256(normalizedSource)" },
  "run": { "timestamp": "ISO8601", "uuid": "string" },
  "logs": [ ... ],
  "steps": [ ... ],
  "callGraph": [ { "from": "string", "to": "string", "atStep": 0 } ],
  "ask": [ ... ],
  "env": { ... },
  "status": "error"?,
  "reason": "string"?
}
```

Where `inputsResolved[*] = { source: "caller"|"default"|"missing", value?, meta: {} }`.

- **CLI:** `loom_vm_cli` supports `--print-logs`, `--print-receipt`, `--result-only`, `--receipt-out`; structured **error receipts**; `module.hash` and run metadata.

## Quickstart

### Requirements
- Python 3.10+ and a virtual environment.

### Install & Run (VM)
```bash
python -m src.loom_vm_cli "./Modules/vm_choose_repeat_call.loom" \
  --in who="guest" --print-logs --print-receipt --receipt-out ./vm_receipt.json
```
**Expected output:**
```
Access: limited
1
2
3
Hello, World!
```

### Interpreter Parity
Use the interpreter for validation and tests; receipts must include `engine:"interpreter"` and `inputsResolved[*].meta = {}`.

## Development Principles
1. Preserve locked invariants and frozen receipt schema.
2. Prefer VM changes; keep interpreter in lockstep for parity/tests.
3. Additions land behind explicit flags/toggles; default remains strict and deterministic.

## Roadmap (Next Steps)
**Must‑do**
- Add `engine:"interpreter"` to interpreter receipts.
- Ensure interpreter receipts include `inputsResolved[*].meta = {}` (reserved for future use).
- Add `--receipt-out`, run metadata, and structured error receipts to `loom_cli`.
- VM: align `Choose` receipts with interpreter (`predicateTrace` + `selected`).
- VM: add `NEG` tests (numeric only, `TypeError` on non‑numeric).
- Repeat: inclusive descending ranges (`5..1`).
- Normalization tests: mixed whitespace → identical AST/hash.

**Should‑do**
- Registry‑strict toggle for both CLIs (emit structured error receipts, not bare exit).
- Receipt schema doc (fields, enums, callGraph, run metadata).
- Rhizome ingest stub (pipe receipts into Rhizome).

**Could‑do**
- Half‑open ranges (start..end exclusive).
- VM debug extras behind `--debug-vm` (record ip/opcodes).

---

**North‑Star UX:** Author an outline → run on VM → inspect a precise receipt of what happened → compose modules into agents (Organisms) → connect them into networks (Rhizomes). LoomWeaver assists as instructioneer, validator, and mentor.

