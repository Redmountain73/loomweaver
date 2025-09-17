#!/usr/bin/env bash
# Idempotent GitHub remote setup. Safe with spaces in path.
set -euo pipefail
ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$ROOT/.."

if git rev-parse --git-dir >/dev/null 2>&1; then
  echo "Git repo detected."
else
  echo "Initializing git repo..."
  git init
  git add .
  git commit -m "init"
fi

if git remote get-url origin >/dev/null 2>&1; then
  echo "Remote 'origin' already set: $(git remote get-url origin)"
else
  echo "No 'origin' remote. To set it:"
  echo "  git remote add origin https://github.com/<your-username>/<your-repo>.git"
  echo "  git branch -M main"
  echo "  git push -u origin main"
fi
