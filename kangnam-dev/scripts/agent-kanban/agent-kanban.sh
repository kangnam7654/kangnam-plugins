#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
KANBAN_ROOT="${PLUGIN_ROOT}/mcp/agent-kanban"

if [[ ! -f "${KANBAN_ROOT}/dist/cli/index.js" ]]; then
  cat >&2 <<EOF
agent-kanban runtime is not built.
Run:
  npm --prefix "${KANBAN_ROOT}" install
  npm --prefix "${KANBAN_ROOT}" run build
EOF
  exit 1
fi

exec node "${KANBAN_ROOT}/dist/cli/index.js" "$@"
