# Sprint Plan Mode Scoring Rubric

Used to evaluate `~/wiki/Projects/<project>/Sprints/<version>/planning.md` files (frontmatter `type: project_spec` and `sprint:` field present).

Primary criterion: **Gate Triple Integrity** (hard gate: >= 8 required for PASS)

## What This Mode Evaluates

A sprint plan is **not** an implementation plan. It defines:

1. The **scope** of one sprint (one or a small handful of measurable readiness gates)
2. The **pace** the user commits to (target duration, daily working time)
3. **Out-of-scope** items explicitly deferred
4. **Sprint intake cards** from Kanban explicitly adopted or deferred
5. **Carry-over** from the previous sprint's review

It is judged by the *integrity of these structures*, never by length.

## ⚠️ Length Bias Prohibition

**NEVER reduce a score because the plan is short.** A sprint may legitimately have one gate and a 2-day pace. The rubric below evaluates structural completeness and specificity, both of which are length-independent. Specifically:

- Do not penalize "few gates" if the plan declares `scale: micro` in frontmatter and the gates that exist are well-formed.
- Do not require a minimum word count for any criterion.
- Do not penalize "Out-of-scope is sparse" — sparse is fine when the sprint is small.

If you find yourself wanting to write feedback like *"the plan should have more detail"* or *"add more gates"*, stop and re-check whether the existing content is well-formed. If it is, score reflects that.

## Scale-Aware Expectations

Read the `scale` field in frontmatter (`micro` | `standard` | `major`, default `standard`). Use it as the input to **Feasibility only** — it does not affect any other criterion.

| Scale | Expected gate count | Expected pace |
|---|---|---|
| `micro` | 1–2 | 1–3 days |
| `standard` | 3–5 | 1–2 weeks |
| `major` | 5+ | 2 weeks+ |

If the plan's gate count or pace falls **outside** the band for its declared scale, that is a Feasibility issue. Inside the band → no Feasibility deduction. Do not second-guess the user's declared scale; if they said `micro`, evaluate against `micro` expectations.

## Scoring System

Each criterion 0–10 (integers only). Same scoring scale as plan mode.

## Weights

| # | Criterion | Weight | What scores 7+ |
|---|-----------|--------|-----------------|
| 1 | **Gate Triple Integrity** | 30% | Every Core Gate has `domain:` (valid enum), `card:` (existing task card id or `new`), `source_epic:` (`none` or an existing epic id), `happy`/`isolation_failure`/`expected_reaction` (concrete content, no placeholders), and per-scenario `검증:` (runnable command or `manual`). Each scenario is a specific verifiable assertion. |
| 2 | **Structural Completeness** | 20% | All five required sections exist as headings: `⏱️ 페이스`, `한 줄 요약`, `Sprint Intake Cards`, `Core Gates`, `Out-of-scope`. Each section has at least some non-placeholder content (carry-over/intake may explicitly say none). |
| 3 | **Specificity** | 20% | Gate descriptions name concrete artifacts (HTTP method + path, file name, function name, command, error message, status code). Vague verbs ("잘 동작", "적절히 처리", "잘 보여준다") are absent or rare. Pace commitment names exact day count and end date, not "약 1주". |
| 4 | **Feasibility** | 15% | Gate count fits the declared `scale`. Pace commitment is internally consistent (목표 기간 × 일 평균 작업 ≈ 끝나는 시점). No physically impossible pace (e.g., 8 gates in 1 day, or 24 hours/day). |
| 5 | **Carry-over Handling** | 15% | If a previous sprint's `review.md` exists with Action Items, each item is either (a) explicitly carried into this sprint as a gate or sub-item, (b) explicitly deferred to `Out-of-scope` with reason, or (c) marked done in the carry-over section. No silent drops. First sprint with no prior review → automatic 7. |

## Sub-item Scoring Formula

Same as plan mode. For each criterion, count sub-conditions in the "What scores 7+" column, divide passed by total, map via this table:

| Pass Ratio | Score |
|---|---|
| 100% | 10 |
| 88–99% | 9 |
| 75–87% | 8 |
| 63–74% | 7 |
| 50–62% | 6 |
| 38–49% | 5 |
| 25–37% | 4 |
| 13–24% | 3 |
| 1–12% | 2 |
| 0% | 0 |

When a criterion has exactly 1 sub-item, score is binary: 10 if it passes, 3 if not.

## Final Score Calculation

```
Final Score = (Gate Triple × 0.30) + (Structural × 0.20) + (Specificity × 0.20)
            + (Feasibility × 0.15) + (Carry-over × 0.15)
```

Maximum: 10.00. PASS = Total > 8.00 AND Gate Triple Integrity >= 8.

## Gate Triple Integrity — Sub-item Definition

For **each** Core Gate found, count the gate as passing if **all** of:

1. The gate has a concrete, descriptive heading (not `### G1. <게이트 이름>` template residue).
2. A `happy` line exists, contains a verifiable predicate (specific input → specific observable output), no placeholder text.
3. An `isolation_failure` line exists, names a specific failure mode (network down, db unreachable, dep crash, malformed input), no placeholder text.
4. An `expected_reaction` line exists, names a specific automatic system response (retry with backoff, fallback to cached, raise typed error, log + alert), no placeholder text.
5. A `domain:` field is present with **exactly one** of the enum values: `frontend`, `backend`, `mobile`, `data`, `devops`, `ai`. Blank, "fullstack", "all", or any custom label fails.
6. A `card:` field is present and is either `new` or a real task card id listed in `## Sprint Intake Cards`; no card id is reused across gates; epic ids are not used as `card:`.
7. A `source_epic:` field is present and is either `none` or a real epic card id listed in `## Sprint Intake Cards`.
8. Each of the three scenarios (`happy`/`isolation_failure`/`expected_reaction`) has a `검증:` line whose value is either a runnable command (e.g., `pytest tests/...`, `curl ...`, `playwright test ...`) or the literal string `manual`. Empty, "TBD", "나중에", or vague description without a command fails.

The criterion's pass ratio is (gates that pass all 6) / (total gates). Zero gates → score 0.

### Why these matter for downstream automation

Sub-items 5-8 are not mere bureaucracy — they enable `/sprint-implement` and verification:
- `domain` tells the dispatcher which domain agent (`frontend-dev`, `backend-dev`, etc.) builds the gate.
- `card` tells the publisher whether to adopt an existing Backlog/InProgress/Blocked task card or create a new gate card.
- `source_epic` tells the publisher which existing epic a newly created task should belong to.
- `검증` tells the verifier whether to auto-run a command or wait for human verification (memo-only).

A plan that scores low on these sub-items still gets built, but the build/verify steps fall back to manual orchestration — defeating the point of structured planning.

## Specificity Red Flags

These patterns deduct from Specificity (do not cap, but each instance reduces the pass ratio by 1 sub-item equivalent):

- **Vague verbs**: "잘", "적절히", "필요시", "원활하게", "smoothly", "properly"
- **Vague nouns**: "관련 기능", "필요한 것", "기타 등등", "etc."
- **Unbounded scope**: "...을 포함한 여러 기능", "and more"
- **Pace without date**: "약 1주", "며칠 안에", "대략 빨리" (must be `<N>일/주` AND `<YYYY-MM-DD>`)

Do not flag domain shorthand the user has clearly defined elsewhere in the plan (e.g., a project glossary).

## Carry-over Handling — Decision Tree

1. Does the plan contain a `## 직전 스프린트 Carry-over` section? If no → score 0.
2. Read the section. Is it `_(첫 스프린트 — carry-over 없음)_`? → score 7 (no prior review to evaluate against).
3. Is it `_(...에 Action Items 없음)_`? → score 7 (verifiable).
4. Otherwise, the section lists items from the previous review's Action Items. For each item, check whether it appears (verbatim or rephrased) as either:
   - a Core Gate or sub-item, OR
   - an entry in `## Out-of-scope` with a reason, OR
   - a checked-off line in carry-over itself.
5. Pass ratio = handled / listed. Map via the standard table.

## Sprint Intake Handling — Structural Check

If `## Sprint Intake Cards` lists card ids:
- task ids must appear exactly once as a Core Gate `card:` value, OR in `## Out-of-scope` with a reason.
- epic ids must appear at least once as a Core Gate `source_epic:` value, OR in `## Out-of-scope` with a reason.

Unmapped intake cards are a Structural Completeness failure. A plan with no intake cards can state that explicitly and does not lose points.

## Edge Cases

### `--allow-unfrozen` / draft plans
- Same scoring. No relaxation. Drafts that pass are drafts that pass.

### Plan refers to external doc instead of inline content
- A gate written as "happy: see [[../../Specs/Auth.md#happy-path]]" — score the *reference* itself: does it point to a file/anchor that exists? If yes, treat the linked content as if inline. If no, score that sub-item 0 with feedback "broken reference".
- Do not follow the link to *score the linked content* — that's out of scope. Only verify it exists.

### User declares an unusual scale
- Honor the declared scale. If a user declares `scale: major` for a 1-gate plan, that's a Feasibility issue (gate count below band), not a license to redefine the scale.

### Criteria that do not apply
- NEVER score N/A. First sprint with no prior review → Carry-over scored 7 (see decision tree).
- A plan with zero Core Gates → Gate Triple Integrity is 0; this also forces REJECT via the primary-criterion gate.

### User explicitly requesting lower standards
- REFUSE. Same as plan mode. Threshold is fixed.

## Output Notes

- In feedback, **never** write "the plan needs more detail" without naming the specific sub-condition that failed.
- When citing a sub-condition failure, quote the offending line from the plan and name the specific rubric clause it violated.
- Acceptable feedback: *"Sub-condition 1.2 'happy line names a verifiable predicate' fails for G2 — line reads `요청을 잘 처리한다` which is a vague verb (Specificity red flag)."*
- Unacceptable feedback: *"G2 needs more detail."*
