#!/usr/bin/env bash
# Developer setup for a fresh clone of sage_tree_converter.
#
#   1. Enables the project git hooks. The commit-msg hook rejects any commit
#      message that contains non-ASCII characters or a Co-authored-by trailer.
#   2. Installs the package in editable mode with its dev tools (ruff,
#      basedpyright, pytest), so `make lint`, `make typecheck`, `make fmt`
#      and `make test` work.
#
# Run once, from anywhere, after cloning:
#   ./scripts/setup-dev.sh
set -euo pipefail

# Move to the repository root (this script lives in scripts/).
cd "$(dirname "$0")/.."

# --- 1. Git hooks ----------------------------------------------------------
git config core.hooksPath .githooks
echo "Enabled git hooks (core.hooksPath = .githooks)."

# --- 2. Python dev tooling -------------------------------------------------
# Use PYTHON_BIN from .env if present, otherwise python3 (matches the Makefile).
PYTHON_BIN="$(grep -E '^PYTHON_BIN=' .env 2>/dev/null | cut -d= -f2- | tr -d '[:space:]' || true)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
echo "Using interpreter: $PYTHON_BIN"

"$PYTHON_BIN" -m pip install -e ".[dev]"

echo
echo "Setup complete."
echo "  make lint       # ruff check"
echo "  make typecheck  # basedpyright"
echo "  make fmt        # ruff format + ruff check --fix"
echo "  make test       # pytest"
echo
echo "Commit messages are checked by .githooks/commit-msg:"
echo "  ASCII only, and no Co-authored-by trailer."
