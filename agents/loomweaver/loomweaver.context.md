# Loomweaver — Context for SA & Nova (2025-09-07 · America/Chicago)

## North Star

- Outline-driven natural language for **any** module/agent (not sample-bound).
- VM-first execution; **no API failures at all** (ZFC totalizes every call).
- Reflexive module↔module / agent↔agent calls within one Program.
- Verifier & validator are **warnings-only by default** (strict opt-in).

## What’s True Right Now

- **Surface → IR**: Outline (surface) compiles to schema-locked AST JSON (IR).
- **Determinism**: Canonical AST → bytecode for a stable **VM**, not direct execution of prose.
- **Tooling** (initial): compiler, AST→VM, runner, peek, and a full snapshot packer.
- **Examples**: Greeting, Score Gate (comparatives), Echo (multi-action “, then …”) compile and run.

## Nova’s critique synthesis (operationalized)

1. **Determinism vs. NL** → Already handled by normalizing to AST; keep grammar flexible but schema strict.
2. **Surface vs. IR** → Locked: outline → AST (IR) → VM code.
3. **Tooling now, not later** → Add CLI + validator + test runner (this commit).
4. **Security / capability model** → Introduce a minimal capabilities schema + policy file (this commit). Enforce at call sites soon.
5. **Testing reality** → Add a conformance-style test runner that executes module tests described in JSON (this commit).

## New Artifacts in this snapshot

- **Schemas/loom-capabilities.schema.json** — capability model (who can call whom; coarse IO gates).
- **agents/loomweaver/loomweaver.capabilities.json** — sample policy for Loomweaver.
- **scripts/validate_program.py** — validates combined Program+Modules against schemas (warnings by default).
- **agents/loomweaver/loomweaver.tests.json** — small, machine-read test bundle.
- **scripts/run_module_tests.py** — executes those tests via VM, reports pass/fail (no hard exits by default).
- **scripts/loom_cli.py** — one CLI for compile / validate / run / test (DX seed).
- **SECURITY.md** — capability-model intent + next steps.

## Near-Term Order of Work (bite-sized)

1. **Wire capabilities into runtime**: VM `CALL` checks a capabilities resolver (warnings-only unless `--strict`).
2. **Cross-module calls** in NL: `call <Module Name> with k=v, then …` → AST `Call` → VM `CALL`, receipt `callGraph`.
3. **Validator hooks in CLI**: `loom validate --strict` for CI; default warns only.
4. **Conformance growth**: grow `agents/*/*.tests.json` and add golden receipts for choose/call/ask.
5. **LSP/Editor affordances** (scaffold): basic diagnostics via CLI JSON (LSP can shell out).

## Defaults / Knobs

- `retry_budget`: 0–3; CB short-open; serve cache when open.
- Validator & test runner: warnings-only exit code 0; `--strict` exits non-zero on failures.
- AST/Schema versioning: `"astVersion": "2.1.0"` at Program and Module.
