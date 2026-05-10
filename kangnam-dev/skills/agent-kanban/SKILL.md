---
name: agent-kanban
description: "Project-local Kanban for LLM development sessions. Use when the user wants an LLM/dev Kanban board, project-local task state, autonomous session tracking, or asks about the agent-kanban CLI/MCP/UI. This is not the personal ~/wiki/Kanban board."
---

# Agent Kanban

Agent Kanban is the project-local board for development sessions. It stores state in the current project, not in `~/wiki`:

```txt
<project-root>/.kanban/kanban-data.json
```

Use the CLI first. It is more token-efficient than MCP because command output is compact and the model does not need to carry many tool schemas. MCP is only a fallback for clients that cannot run shell commands.

## Locate the packaged CLI

Resolve `<plugin-root>` as two directories above this skill directory:

```txt
<plugin-root>/scripts/agent-kanban/agent-kanban.sh
```

Use the wrapper directly unless a global `agent-kanban` binary is already available.

## Session Loop

At session start:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh context --cwd "$PWD"
```

If the output shows an active card, continue it. If it shows ready cards, claim the highest-priority ready card before editing files. If no ready card exists, create one before starting new implementation work.

Create and claim:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh create "Implement settings validation" --cwd "$PWD" --status ready --priority high --next "Write failing validation test"
<plugin-root>/scripts/agent-kanban/agent-kanban.sh claim KBN-1001 --cwd "$PWD" --session "<stable-session-id>"
```

Record progress after meaningful work:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh progress KBN-1001 --cwd "$PWD" --msg "Added validator and tests" --files src/settings.ts,tests/settings.test.ts --test-command "npm test" --test-status passed --test-summary "Relevant tests passed"
```

Finish only after verification:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh done KBN-1001 --cwd "$PWD" --summary "Settings validation implemented and verified" --test-command "npm test" --test-status passed --test-summary "Relevant tests passed"
<plugin-root>/scripts/agent-kanban/agent-kanban.sh end --cwd "$PWD" --session "<stable-session-id>" --outcome completed --summary "Finished KBN-1001"
```

If blocked:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh block KBN-1001 --cwd "$PWD" --reason "Need product decision on validation rules" --next "Ask user for exact rule"
```

## Human UI

The board also has a human-readable web UI. From `<plugin-root>/mcp/agent-kanban`:

```bash
npm install
npm run dev
```

Open `http://127.0.0.1:3001`.

## MCP Fallback

The packaged MCP server is intentionally thin:

- `kanban_context` maps to `agent-kanban context`.
- `kanban_run` accepts the CLI args after the binary name.

Do not prefer MCP when direct CLI execution is available.

## Boundaries

- Do not store agent session state in `~/wiki/Kanban`.
- Do not put project board files inside the plugin. The plugin contains code only.
- Pass `--cwd "$PWD"` or an explicit project directory on every command.
- Use compact text output by default. Use `--json` only when structured data is needed.
