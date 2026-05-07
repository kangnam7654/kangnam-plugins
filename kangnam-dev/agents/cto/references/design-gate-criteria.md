# Design Gate Criteria (#25)

## Purpose

CTO evaluates the entire Design Phase output to decide whether to proceed to Build Phase.

## Required Inputs (all must exist)

1. `arch-spec.md` or its content absorbed into `design-spec.md` — tech stack, DB schema, API design, consistency check results
2. `ux-ui-spec.md` or its content — personas, user flows, design system, mockups, debate resolution
3. Execution plan (#23) — file structure, implementation order, parallel tracks
4. Plan-critic verdict (#24) — PASS status

If any input is missing: decision = `ESCALATE`, reason = "Design Phase 산출물 누락: {missing item}."

## Evaluation Dimensions

| Dimension | What to check |
|---|---|
| **Architecture completeness** | Tech stack ADR exists. DB schema reviewed and passed. API design reviewed and passed. DB-API consistency verified. |
| **UX/UI readiness** | Personas defined. User flows cover primary + secondary scenarios. Design system has colors, typography, spacing, components. Mockups exist for every screen in the user flow. |
| **Plan feasibility** | File structure matches architecture. Implementation order respects dependencies. Parallel tracks don't have hidden dependencies. Estimated effort is bounded. |
| **Cross-phase consistency** | UX/UI screens reference API endpoints that exist. API endpoints reference DB tables that exist. Design tool matches tech stack (HTML/CSS for web, Stitch for RN). |

## Decision Enum

| Decision | Condition | next_step |
|---|---|---|
| `PASS` | All 4 dimensions are satisfactory | #26 (Design Spec 문서화) |
| `ARCH_REVISION` | Architecture issues (missing ADR, unreviewed schema/API, consistency gaps) | #10 (redo tech stack) |
| `UXUI_REVISION` | UX/UI issues (missing personas, incomplete flows, no mockups) | #17 (redo UX design) |
| `PLAN_REVISION` | Plan issues (unrealistic order, missing dependencies, no file structure) | #23 (redo execution plan) |
| `ESCALATE` | Compound failure across 2+ dimensions, or missing inputs | Report to user |

## Loop Limit

`loop_count` increments on every non-PASS decision. At loop_count = 10: force `ESCALATE` with message "Design Phase 해결 불가. 10회 반복 실패." and halt pipeline.
