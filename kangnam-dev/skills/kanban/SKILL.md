---
name: kanban
description: "Project-local Kanban for LLM development sessions. Use when the user mentions kanban, 칸반, board, 보드, current work, backlog, ready, in progress, blocked, review, done, or project task tracking. This skill uses each project's .kanban/kanban-data.json, not ~/wiki/Kanban."
---

# Kanban

This skill is now a compatibility alias for `agent-kanban`.

Use the project-local board by default:

```txt
<project-root>/.kanban/kanban-data.json
```

Do not create, move, or update LLM development cards in `~/wiki/Kanban`. The old wiki board is only for explicitly requested personal/global tracking.

## Locate the CLI

Resolve `<plugin-root>` as two directories above this skill directory:

```txt
<plugin-root>/scripts/agent-kanban/agent-kanban.sh
```

Use the wrapper directly:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh context --cwd "$PWD"
```

## Default Session Flow

At the start of repo work:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh context --cwd "$PWD"
```

If no ready card exists and the work is substantial, create one before editing:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh create "작업 제목" --cwd "$PWD" --status ready --priority medium --next "다음 행동"
```

Claim work before implementation:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh claim KBN-1001 --cwd "$PWD" --session "<stable-session-id>"
```

Record meaningful progress:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh progress KBN-1001 --cwd "$PWD" --msg "진행 내용" --files src/file.ts --test-command "npm test" --test-status passed --test-summary "관련 테스트 통과"
```

Finish only after verification:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh done KBN-1001 --cwd "$PWD" --summary "검증 후 완료" --test-command "npm test" --test-status passed --test-summary "관련 테스트 통과"
```

## Human UI

From `<plugin-root>/mcp/agent-kanban`:

```bash
npm install
npm run dev
```

Open `http://127.0.0.1:3001`.

## Boundaries

- Project development state belongs in the repo-local `.kanban/` directory.
- Always pass `--cwd "$PWD"` or an explicit project path.
- Do not use the old wiki card scripts unless the user explicitly asks for the personal/global wiki Kanban.
