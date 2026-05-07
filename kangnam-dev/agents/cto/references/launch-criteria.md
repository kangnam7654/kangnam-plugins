# Launch Criteria (#35)

## Purpose

CTO evaluates technical readiness for launch as part of the 3-party debate (CEO↔CTO↔CSO).

## Scoring Criteria

| Criterion | Weight | Score 0-10 | What to evaluate |
|---|---|---|---|
| **Code completeness** | 0.30 | | All files in execution plan are implemented. No TODO/FIXME markers in production code. All API endpoints functional. |
| **Test coverage** | 0.25 | | Unit tests exist for business logic. Integration tests for API endpoints. Coverage >= 80%. All tests pass. |
| **Build stability** | 0.20 | | App builds without errors. App runs with the documented run command. No runtime crashes on primary user flows. |
| **Review resolution** | 0.15 | | All DBA review items resolved. All code review items resolved. All security review items resolved or accepted with documented risk. |
| **Design parity** | 0.10 | | Implemented UI matches design-spec mockups. API responses match API design schema. DB migrations match schema design. |

## PASS Condition

- Total > 8.0 (weighted average)
- Primary criterion (Code completeness, weight 0.30) >= 7

## Output

Submit as `review-verdict` YAML to the 3-party debate mediator (main model). The CTO's verdict is one of three inputs (alongside CEO and CSO verdicts) to the consensus process.

## Technical Readiness Levels

| Total score | Readiness |
|---|---|
| >= 9.0 | Launch-ready. No reservations. |
| 8.0 - 8.9 | Launch-ready with minor items. List items as feedback. |
| 6.0 - 7.9 | Not launch-ready. Specific blockers listed. Recommend code revision (#27). |
| < 6.0 | Significant gaps. Recommend design revision or user escalation. |
