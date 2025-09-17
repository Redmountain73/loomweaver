# SPEC-CODEX-000 — IDE Pairing (Codex in VS Code)

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
