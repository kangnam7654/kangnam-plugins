# ADR Template

Write to `docs/adr/ADR-NNN-<slug>.md`. NNN is the next sequential number after the highest existing ADR.

## When to Write an ADR

- Decision affects 3+ source files
- Decision introduces a new external dependency
- Decision changes data flow between 2+ components
- Decision constrains future options (choosing a database, adopting a framework)

## When to Skip (inline rationale instead)

- Decision affects 1-2 files within a single module
- Decision is trivially reversible (variable naming convention)

## Template

```markdown
# ADR-NNN: [Decision Title]

## Status
Proposed | Accepted | Deprecated | Superseded by ADR-XXX

## Date
YYYY-MM-DD

## Context
[Why this decision is needed. 2-5 sentences, no vague language.]

## Decision Drivers
- [Quality attribute 1 with measurable target]
- [Quality attribute 2 with measurable target]
- [Constraint 1]

## Considered Options

### Option A: [Name]
- **Description**: [1-2 sentences]
- **Trade-off scores**: Complexity: X, Performance: X, Maintainability: X, Time-to-implement: X, Durability: X → Weighted: X.XX

### Option B: [Name]
- **Description**: [1-2 sentences]
- **Trade-off scores**: [same format]

## Decision
[Which option was chosen and 1-2 sentence rationale tied to weighted scores.]

## Consequences

### Positive
- [Concrete benefit with measurable impact]

### Negative
- [Concrete drawback with measurable impact]

### Risks
- [Risk]: [Mitigation]

## Follow-up Actions
- [ ] [Specific action for specific agent]
```
