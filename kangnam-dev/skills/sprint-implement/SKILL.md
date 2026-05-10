---
name: sprint-implement
description: "Implement the active project-local sprint. Use when the user asks to continue a sprint, execute sprint tasks, or run the implement phase after sprint planning."
---

# Sprint Implement

Use this skill to execute selected sprint tasks from the current project's Agent Kanban board.

## Canonical Command

The full workflow is defined in:

```txt
<plugin-root>/commands/sprint-implement.md
```

Resolve `<plugin-root>` as two directories above this skill directory.

## Codex Execution Notes

- Load the active sprint cards from `<project-root>/.kanban/kanban-data.json`.
- Use the three-phase sprint model: `planning`, `implement`, `review`.
- Claim or move each task through the project-local board as work starts, progresses, and finishes.
- If the command file contains Claude-style `Agent(...)` blocks, treat them as role guidance. Execute locally unless this session explicitly allows sub-agent delegation.
- Follow the repo's normal test/build checks for each changed area.
- End with completed cards, remaining cards, verification results, and the next sprint phase.
