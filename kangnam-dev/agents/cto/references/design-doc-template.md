# Design Document Template

Write to `docs/llm/<feature-or-topic>.md` for LLM-facing design documents.

## Required Sections

```markdown
# Design: [Feature/Topic Name]

## Date
YYYY-MM-DD

## Status
Draft | Under Review | Approved | Implemented

## Requirements

### Functional
- [FR-1]: [Description] — [CONFIRMED / ASSUMED / TBD]

### Quality Attributes
- [QA-1]: [Measurable target] — [CONFIRMED / PROPOSED / TBD]

### Constraints
- [C-1]: [Description]

## Proposed Architecture

### Architecture Diagram
![Architecture](./architecture.png)
[Mermaid source in ./architecture.mmd]

### Components

#### [Component Name]
- **Responsibility**: [1-2 sentences]
- **Inputs**: [What it receives, from whom, in what format]
- **Outputs**: [What it produces, for whom, in what format]
- **Owned data**: [What data store(s) it exclusively writes to]
- **Failure behavior**: [What happens when this component is down for 5 minutes]

### Integration Contracts

| From | To | Method | Data Format | Error Contract |
|---|---|---|---|---|
| Component A | Component B | REST POST /path | JSON schema | 4xx: no retry; 5xx: exponential backoff max 3 |

### Data Flow
[Step-by-step for the primary use case]

## Trade-Off Analysis
[Full Trade-Off Framework table]

## Failure Modes
| Component | Failure | Impact | Detection | Recovery |
|---|---|---|---|---|

## ADR Reference
- ADR-NNN: [Title]

## Open Questions
| # | Question | Blocks | Default assumption | Who answers |
|---|---|---|---|---|
```
