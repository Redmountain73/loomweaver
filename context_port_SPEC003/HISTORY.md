# Project History (Up to SPEC-003)

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
