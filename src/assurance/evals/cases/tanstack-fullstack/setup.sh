#!/usr/bin/env bash
# Install fixture dependencies before the agent runs.
# Runs in the workspace directory.
set -euo pipefail

if command -v pnpm &>/dev/null; then
  echo "  [setup] Installing dependencies with pnpm..."
  pnpm install 2>&1 | tail -5
else
  echo "  [setup] pnpm not found, falling back to npm..."
  npm install 2>&1 | tail -5
fi
