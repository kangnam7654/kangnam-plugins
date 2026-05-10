# Agent Kanban Project Instructions

This project builds a local Kanban board for human-visible development tracking and LLM-accessible task state.

## Local Commands

- Install dependencies: `npm install`
- Run web UI and API in development: `npm run dev`
- Build production assets: `npm run build`
- Run built server: `npm start`
- Run built CLI: `npm run cli -- <command>`
- Run MCP server after build: `npm run mcp`
- Run tests: `npm test`
- Run type checks: `npm run typecheck`

## Kanban Usage

Use the `agent-kanban` CLI for development task state when shell access is available. Use the MCP adapter only when the client cannot run the CLI directly.

At session start:
- Run `agent-kanban context --cwd <current-project-dir>` or `agent-kanban start --cwd <current-project-dir> --session <stable-id>`.
- The board state is project-local: commands write to `<project-root>/.kanban/kanban-data.json` based on `cwd`.
- Continue an active card when one is printed.
- If no active card exists, claim the highest-priority ready card before editing files.
- If no ready card exists, create a task before starting new implementation work. If the work is broad, create an epic first and put concrete tasks under it.

During work:
- Run `agent-kanban claim <card-id> --cwd <current-project-dir> --session <stable-id>` before file changes for a card.
- Include the same current `cwd` in mutation commands so the CLI routes to the right project-local board.
- Run `agent-kanban progress ...` after meaningful implementation steps, including changed files and test results when available.
- Run `agent-kanban block ...` with a concrete blocker when work cannot continue.

At finish:
- Run `agent-kanban done ...` only after verification.
- Run `agent-kanban end ...` with a concise handoff summary before ending the turn.

Epic model:
- Broad work uses `agent-kanban create "..." --type epic`.
- Concrete work uses `agent-kanban create "..." --type task --epic <epic-id>`.
- The UI renders each epic as a swimlane with Backlog, Ready, In Progress, Review, Blocked, and Done below it.

MCP fallback:
- `kanban_context` maps to `agent-kanban context`.
- `kanban_run` accepts the CLI args after the binary name.

See `docs/AGENTS-kanban.md` for a reusable snippet for other projects.
