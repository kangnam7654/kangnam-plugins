#!/usr/bin/env bash
# Start the local reviewers MCP server for kangnam-dev.
#
# The reviewers backend must already be running on REVIEWERS_BACKEND_URL
# (default: http://127.0.0.1:8787). This script only provides the stdio MCP
# process that Codex/Claude/plugin hosts connect to.

set -euo pipefail

REVIEWERS_ROOT="${REVIEWERS_ROOT:-$HOME/projects/reviewers}"
REVIEWERS_BACKEND_URL="${REVIEWERS_BACKEND_URL:-http://127.0.0.1:8787}"
export REVIEWERS_BACKEND_URL

if [[ ! -d "$REVIEWERS_ROOT" ]]; then
  echo "reviewers repo not found: $REVIEWERS_ROOT" >&2
  echo "Set REVIEWERS_ROOT to the reviewers repo path." >&2
  exit 2
fi

if [[ -x "$REVIEWERS_ROOT/target/debug/reviewers-mcp" ]]; then
  exec "$REVIEWERS_ROOT/target/debug/reviewers-mcp"
fi

exec cargo run --manifest-path "$REVIEWERS_ROOT/Cargo.toml" -p reviewers-mcp --quiet
