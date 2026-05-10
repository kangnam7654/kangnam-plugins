# Plan Mode Scoring Rubric

Primary criterion: **Clarity** (hard gate: Clarity >= 8 required for PASS)

## Scoring System

Each criterion is scored **0–10** as integers only. No half points.

| Score | Meaning |
|-------|---------|
| 0–2   | **Missing** — criterion is not addressed at all |
| 3–4   | **Weak** — addressed but with critical gaps |
| 5–6   | **Partial** — some sub-items meet the bar, others do not |
| 7–8   | **Solid** — meets the bar with minor gaps |
| 9–10  | **Excellent** — fully meets or exceeds the bar |

## Weights

| # | Criterion | Weight | What scores 7+ |
|---|-----------|--------|-----------------|
| 1 | **Clarity** | 30% | Every task answers: what (concrete deliverable), who (single owner), done-when (measurable exit condition). Zero ambiguous words ("적절히", "등", "as needed"). |
| 2 | **Completeness** | 20% | All steps from start to goal are present. Setup, migration, deployment, cleanup included. No "and then somehow it works" gaps. |
| 3 | **Feasibility** | 15% | Scope fits stated constraints (time, team, tech). No tasks that require unavailable resources or unproven technology without a spike. |
| 4 | **Dependencies** | 15% | Execution order is correct. Blocking deps explicitly marked. Parallel-capable tasks are identified. No circular dependencies. |
| 5 | **Risk Coverage** | 10% | Top 3 failure modes identified with mitigation. Assumptions stated. High-risk steps have rollback plan. |
| 6 | **Scope Alignment** | 10% | Plan scope == requested scope. No scope creep (extra unrequested work). No scope gap (missing requested parts). |

## Sub-item Scoring Formula

For each criterion, count the sub-items defined in the "What scores 7+" column. Calculate the pass ratio and map to a score:

| Pass Ratio (passed / total sub-items) | Score |
|----------------------------------------|-------|
| 100% (all sub-items pass)              | 10    |
| 88–99%                                 | 9     |
| 75–87%                                 | 8     |
| 63–74%                                 | 7     |
| 50–62%                                 | 6     |
| 38–49%                                 | 5     |
| 25–37%                                 | 4     |
| 13–24%                                 | 3     |
| 1–12%                                  | 2     |
| 0% (none pass)                         | 0     |

When a criterion has exactly 1 sub-item, score is binary: 10 if it passes, 3 if it does not.

## Final Score Calculation

```
Final Score = (Clarity × 0.30) + (Completeness × 0.20) + (Feasibility × 0.15)
            + (Dependencies × 0.15) + (Risk × 0.10) + (Scope × 0.10)
```

Maximum: 10.00

## Clarity Red Flags

These patterns cap Clarity at **7 maximum** (prevents 8+ but does not force REJECT on its own):

- "적절히 처리", "필요에 따라", "기타"
- "refactor as needed", "handle edge cases", "proper error handling", "use your judgment"
- Tasks without a concrete deliverable (no artifact named)
- Steps described as "연구", "검토", "조사" without a defined output artifact and time-box
- Vague owners when context indicates a team: "팀", "담당자", "someone"
- Unbounded lists ending with "..." or "and more"

Note: "등" is natural Korean enumeration and is NOT a red flag when used after 3+ concrete items (e.g., "Python, Go, Rust 등"). Flag only when "등" replaces specifics (e.g., "필요한 도구 등을 설치").

## Edge Cases

### Single-task plans (1 step only)

- **Dependencies**: A single-task plan has no inter-task dependencies to evaluate. Score Dependencies as 7 (default baseline). Rationale: absence of complexity is not a flaw, but the plan has not demonstrated dependency management either.
- **Completeness**: Still evaluate whether the single task covers all work from start to goal. A single task that omits setup or cleanup scores below 7.

### Research / spike / investigation plans

- **Clarity "done-when"**: Research tasks must define a concrete output artifact (document, decision record, prototype, benchmark result) and a time-box (maximum duration after which the task ends regardless of outcome). If both are present, "done-when" sub-item passes. If either is missing, it fails.
- **Risk Coverage**: For spikes, "top 3 failure modes" includes: (1) spike exceeds time-box, (2) spike produces inconclusive results, (3) chosen approach proves infeasible. The plan must address at least these three.

### Non-software plans (documentation, process, migration)

- Apply the same 6 criteria. "Deliverable" means the output artifact (document, runbook, migrated data). "Deployment" in Completeness means the delivery/publication step. Do not skip criteria because the plan is not code.

### Partial or draft plans

- If the user explicitly labels the plan as "draft", "WIP", or "partial": score what is present using the same rubric. Do not infer missing sections as intentional omissions. Mark missing sections as score 0–2 for the relevant criterion. In the feedback, note that the plan is incomplete and identify the single most critical gap.

### Plans with no explicit owner (solo project)

- If context indicates a solo developer (single person, personal project, or no team mentioned), treat "who" sub-item in Clarity as automatically passing. The solo developer is the implicit owner of all tasks.
- If context does NOT indicate solo vs. team: flag missing "who" as a Clarity gap. Do not assume.

### Criteria that do not apply (N/A handling)

- NEVER score a criterion as "N/A". Every criterion always receives a numeric score 0–10.
- If a criterion's sub-items are trivially satisfied because the plan's nature makes them irrelevant (example: Dependencies for a single-task plan), score that criterion as **7**. This reflects "no issues found, but no positive evidence of quality either."

### User explicitly requesting lower standards

- If the user asks to lower the PASS threshold, relax criteria, or skip scoring: REFUSE. Respond with: "PASS threshold (Total > 8.00, Clarity >= 8) is fixed. I can help you improve the plan to meet it." Then proceed with normal scoring.
