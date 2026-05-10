# Agent Kanban

Agent Kanban is a local development board designed for two audiences:

- humans who need a readable UI for ongoing implementation work
- LLM sessions that need durable task state without burning tokens on large tool schemas

The durable state lives inside each project at `.kanban/kanban-data.json`. The CLI, web UI, API, and optional MCP adapter all route by `cwd`, so agents and humans see the same project-local board.

## What is included

- React board UI with columns, filters, drag/drop moves, card details, progress logs, blockers, files, and test evidence
- Local REST API for the UI
- Token-efficient `agent-kanban` CLI for LLM sessions
- Thin stdio MCP adapter for clients that cannot run the CLI directly
- File-backed project-local persistence with an explicit `KANBAN_DATA_PATH` override for special cases
- Agent workflow commands: context, start, list, create, claim, move, progress, block, done, end

## Run locally

```sh
npm install
npm run dev
```

Open `http://127.0.0.1:3001`.

Production build:

```sh
npm run build
npm start
```

MCP server after build:

```sh
npm run mcp
```

Development MCP server:

```sh
npm run dev:mcp
```

## CLI usage

Use the CLI first when the agent can run shell commands. It keeps the context small because output is compact text by default and JSON is opt-in.

```sh
agent-kanban context --cwd /Users/kangnam/projects/example-app
agent-kanban create "Add settings validation" --cwd /Users/kangnam/projects/example-app --status ready --priority high --next "Write failing validation test"
agent-kanban claim AK-1 --cwd /Users/kangnam/projects/example-app --session codex-20260510
agent-kanban progress AK-1 --cwd /Users/kangnam/projects/example-app --msg "Added validator and unit test" --files src/settings.ts,tests/settings.test.ts --test-command "npm test" --test-status passed --test-summary "Settings tests passed"
agent-kanban done AK-1 --cwd /Users/kangnam/projects/example-app --summary "Settings validation is implemented and verified"
```

The default output is intentionally line-oriented:

```txt
AK-1 status=in_progress priority=high title="Add settings validation" next="Write failing validation test"
```

Use `--json` only when a client needs structured data.

## MCP registration shape

Use this shape in a local MCP client config, adapted to that client's exact file format:

```json
{
  "mcpServers": {
    "agent-kanban": {
      "command": "npm",
      "args": ["--prefix", "/Users/kangnam/projects/kanban_client", "run", "mcp"],
      "env": {}
    }
  }
}
```

For active development without building first:

```json
{
  "mcpServers": {
    "agent-kanban-dev": {
      "command": "npm",
      "args": ["--prefix", "/Users/kangnam/projects/kanban_client", "run", "dev:mcp"],
      "env": {}
    }
  }
}
```

The MCP adapter exposes only:

- `kanban_context`: compact read-only context for session start
- `kanban_run`: explicit `agent-kanban` CLI command runner

This keeps MCP available without making it the primary, token-heavy interface.

## Architecture choice

The recommended shape is CLI-first, plugin-packaged, MCP-optional:

1. Shared board store writes project-local state.
2. CLI is the default LLM interface.
3. REST API and React UI make the board readable for humans.
4. MCP adapter delegates to the CLI for clients that require MCP.
5. Plugin packaging installs the CLI/MCP/UI code, but never stores project state inside the plugin.

## Project-local data path

Default for a session with `cwd=/Users/kangnam/projects/example-app`:

```sh
/Users/kangnam/projects/example-app/.kanban/kanban-data.json
```

The server finds the project root by walking upward from `cwd` until it sees a marker such as `.git`, `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, or `AGENTS.md`.

Explicit override for tests or one-off shared boards:

```sh
KANBAN_DATA_PATH=/absolute/path/to/kanban-data.json npm run dev
```

Normal LLM usage should pass the current project `cwd` to MCP tools and avoid setting `KANBAN_DATA_PATH`.
