---
name: sprint-planning
description: "Start a project-local development sprint. Use when the user asks for sprint planning, sprint start, sprint backlog selection, or planning/implement/review sprint workflow setup."
---

# Sprint Planning

Use this skill to turn the current project's Agent Kanban backlog into a concrete sprint plan.

## Canonical Command

The full workflow is defined in:

```txt
<plugin-root>/commands/sprint-planning.md
```

Resolve `<plugin-root>` as two directories above this skill directory.

## Codex Execution Notes

- Work only with the project-local board at `<project-root>/.kanban/kanban-data.json`.
- Do not use `~/wiki/Kanban` for project sprint state.
- Keep the active sprint flow to three phases: `planning`, `implement`, `review`.
- If the command file contains Claude-style `Agent(...)` blocks, treat them as role guidance. Execute the work locally unless this session explicitly allows sub-agent delegation.
- Before editing implementation files, ensure the selected work is represented by an epic and concrete task cards.
- End planning with a short sprint scope, selected cards, gate list, and the next command the user should run.
