# MCP Adapter Contract

The server name is `agent-kanban`.

Board state is project-local. The MCP server resolves the project root from the `cwd` argument and writes to:

```txt
<project-root>/.kanban/kanban-data.json
```

Use `KANBAN_DATA_PATH` only for tests or intentional one-off overrides.

## Tools

- `kanban_context`: compact read-only context for session start. This maps to `agent-kanban context`.
- `kanban_run`: runs one explicit `agent-kanban` CLI command. This is the mutation path and keeps MCP schema overhead small.

Examples:

```json
{ "cwd": "/Users/kangnam/projects/example-app", "branch": "main", "session": "codex-20260510" }
```

```json
{ "args": ["create", "Settings UX cleanup", "--cwd", "/Users/kangnam/projects/example-app", "--type", "epic", "--status", "ready"] }
```

```json
{ "args": ["create", "Add settings validation", "--cwd", "/Users/kangnam/projects/example-app", "--type", "task", "--epic", "KBN-1001", "--status", "ready"] }
```

```json
{ "args": ["claim", "KBN-1002", "--cwd", "/Users/kangnam/projects/example-app", "--session", "codex-20260510"] }
```

```json
{ "args": ["progress", "KBN-1002", "--cwd", "/Users/kangnam/projects/example-app", "--msg", "Added validation tests", "--files", "src/settings.ts,tests/settings.test.ts"] }
```

## Board hierarchy

The UI groups work as epic swimlanes:

```txt
Epic
  Backlog | Ready | In Progress | Review | Blocked | Done
    Task cards
```

Use `--type epic` for broad outcomes and `--type task --epic <epic-id>` for implementation cards.

## Expected agent loop

```mermaid
sequenceDiagram
  participant Agent
  participant CLI as agent-kanban CLI
  participant MCP as Optional MCP Adapter
  participant Store as Board Store

  Agent->>CLI: agent-kanban context --cwd project
  CLI->>Store: read <project-root>/.kanban/kanban-data.json
  Store-->>CLI: compact context
  CLI-->>Agent: active/ready cards
  Agent->>CLI: agent-kanban claim AK-1 --cwd project --session id
  Agent->>CLI: agent-kanban progress AK-1 ...
  Agent->>CLI: agent-kanban done AK-1 ... or block AK-1 ...
  Agent->>MCP: kanban_run(args) when CLI cannot be called directly
  MCP->>CLI: delegate to agent-kanban
```
