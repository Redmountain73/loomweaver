#!/usr/bin/env python3
# Rewrites readme.md with SPEC-003 overlay docs appended.
import os

ROOT = r"/workspaces/Loom vs code files"
README = os.path.join(ROOT, "readme.md")

content = """# Loom — Natural Outline Programming Language 

**Loom** is a natural outline programming language: **executable, modular, reflexive**. It’s the **post-Python, post-JSON substrate** where humans and machines share the same language.

## Vision
- A single outline that is readable by people **and** executable by machines.
- Deterministic by construction: **normalize → canonicalize → hash** over normalized source.
- **Auditable by default** via first-class receipts capturing provenance, predicate traces, selections, call graphs, and run metadata.
- Composable at every scale: Atoms (actions) → Organs (modules) → Organisms (agents) → Rhizomes (networks) → Ecosystem.
- Operationally pragmatic: **VM-first** runtime with interpreter parity for tests and validation.

## Purpose
- **Unify code, data, and intent** in outline form—no spec/exec drift.
- **Reproducible runs** with stable identity (hash of normalized source).
- **Strong semantics**: boolean-only truthiness; defined operator precedence.
- **Tooling that proves what happened**: receipts, call graphs, predicate traces.

## Not a JSON Skin (or sugary DSL)
- JSON/YAML are interchange formats; Loom’s outline is the **source of truth** and identity.
- Small, orthogonal verbs (Make, Show, Ask, Return, Choose, Repeat, Call, **NEG**) with strict semantics.
- Runtime + receipts + tooling are first-class parts of the language, not afterthoughts.

## Ontology & Intelligence Layer
- **Atoms** (actions) → **Organs** (modules) → **Organisms** (agents) → **Rhizomes** (networks) → **Ecosystem** (interconnected).
- **LoomWeaver**: the intelligence layer (instructioneer, validator, mentor).

## Locked Invariants (do not break)
- **Runtime:** VM-first execution; interpreter retained for parity/tests.
- **Normalization:** outline text (2/4/6 indent) → canonical → **hash over normalized source only**.
- **Parser:** clause promotion for `when/else if/otherwise`; Repeat header fuse/split.
- **Semantics:** operator precedence `not > and > or > comparisons > arithmetic`; **strict boolean-only truthiness**.
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
