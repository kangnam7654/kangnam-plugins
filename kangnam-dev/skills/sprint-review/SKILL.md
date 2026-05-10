---
name: sprint-review
description: "Review and close a project-local sprint. Use when the user asks for sprint review, retrospective, completed-work summary, or the review phase after implementation."
---

# Sprint Review

Use this skill to review the active sprint, record outcomes, and prepare the next sprint.

## Canonical Command

The full workflow is defined in:

```txt
<plugin-root>/commands/sprint-review.md
```

Resolve `<plugin-root>` as two directories above this skill directory.

## Codex Execution Notes

- Read the project-local board at `<project-root>/.kanban/kanban-data.json`.
- Keep review scoped to the completed sprint work and its verification evidence.
- Use the three-phase sprint model: `planning`, `implement`, `review`.
- If the command file contains Claude-style `Agent(...)` blocks, treat them as role guidance. Execute locally unless this session explicitly allows sub-agent delegation.
- Do not write to `~/wiki` unless the user explicitly asks for that destination.
- End with done items, unresolved items, verification gaps, and candidate backlog items for the next sprint.
