# Loom Security & Capability Model (v0)

## Philosophy

- Default-deny: Modules may not call each other or touch IO unless explicitly allowed.
- Human-friendly policy: JSON schema-validated, committed in repo, reviewed in PRs.
- Runtime totalization: Even capability denials become **explicit receipts**, not silent failures.

## Artifacts

- `Schemas/loom-capabilities.schema.json` — schema for program-level capabilities.
- `agents/<agent>/<agent>.capabilities.json` — per-program policy.

## Next steps

- VM `CALL` checks policy; without allow-rule, emit degraded receipt (`synthetic_ok`, reason="capability denied"), **not** exception.
- Add `--strict` mode to fail hard in CI.
- Add scoped resources (net/fs) gates in execution wrappers.
