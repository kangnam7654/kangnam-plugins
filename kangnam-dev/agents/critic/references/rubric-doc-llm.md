# LLM Mode Scoring Rubric

Same 0–10 integer scale and score-band definitions as HUMAN mode.

| Score | Meaning |
|-------|---------|
| 0–2   | **Missing** — criterion not addressed at all |
| 3–4   | **Weak** — present but critically flawed (fails more than half the sub-conditions) |
| 5–6   | **Partial** — meets some sub-conditions, fails others |
| 7–8   | **Solid** — meets all sub-conditions with at most 1 minor gap |
| 9–10  | **Excellent** — meets every sub-condition with zero gaps |

## Criteria & Weights

| # | Criterion | Weight | Scores 7+ when ALL of these are true |
|---|-----------|--------|---------------------------------------|
| 1 | **Precision** | 30% | (a) Every instruction passes all 5 checks: Specific (names exact values/paths/tools), Unambiguous (only one valid interpretation), Testable (a third party can verify compliance), Complete (no implicit prerequisites), Bounded (finite scope — no open-ended lists). (b) Zero vague words from the red-flag list appear anywhere in the document. (c) Every conditional instruction has an explicit else-branch or default. |
| 2 | **Executability** | 25% | (a) An LLM can follow every instruction without asking a clarifying question. (b) Workflow steps are numbered and in the exact execution order. (c) Every output has an exact template (not a prose description of the format). (d) All referenced tools, files, and paths are named explicitly. (e) No step requires information not provided in the document or available from tools. |
| 3 | **Boundary Clarity** | 20% | (a) In-scope actions are listed explicitly. (b) Out-of-scope actions are listed explicitly with NEVER rules. (c) Every trigger condition is mutually exclusive with other agents/skills (no two triggers can match the same input). (d) ALWAYS and NEVER rules cover the most common misuse patterns (at least 3 NEVER rules). |
| 4 | **Edge Cases** | 10% | (a) At least 5 ambiguous situations are listed with explicit resolution rules. (b) Fallback behavior is defined for every conditional branch (no condition lacks a default). (c) Error states are listed with recovery actions. (d) Input boundaries are defined (what constitutes valid vs. invalid input). |
| 5 | **Consistency** | 15% | (a) No two instructions contradict each other. (b) The same concept is referred to by the same term throughout (no synonyms for the same entity). (c) Priority order is explicit when rules conflict. (d) Formatting conventions (heading levels, list styles, code block usage) are uniform throughout. (e) **Cross-reference integrity**: every step number, section number, or identifier referenced elsewhere in the document points to a step/section that exists AND has the correct name/role. Example check: if a FAIL route says "→ #11" verify that #11 exists and is the correct recovery target (e.g., a design step, not a review step). (f) **Numerical consistency**: counts and totals in summary sections match the actual items in detail sections. Example check: if a summary says "7 agents" verify by counting the actual agent entries. (g) **Recovery route validity**: every failure/recovery target references a step whose role matches the recovery intent — a "schema revision" route must point to a schema design step, not a review or documentation step. |

## Score Calculation

```
Total = (Precision × 0.30) + (Executability × 0.25) + (Boundary Clarity × 0.20)
      + (Edge Cases × 0.10) + (Consistency × 0.15)
```

**Primary criterion**: Precision. PASS requires Precision >= 8.

## Red Flags (auto cap Precision at 5)

If ANY of these are present, Precision cannot exceed 7:
- Any of these vague words/phrases: "적절히", "필요에 따라", "기타", "as needed", "handle edge cases", "use your judgment", "respond appropriately", "when appropriate", "if necessary"
- Contradictory instructions (e.g., "Be concise but thorough")
- Output format described in prose instead of an exact template with literal delimiters
- Unbounded lists: "such as X, Y, Z, and more" or "X, Y, Z 등" (where "등" replaces specifics)
- Any instruction with no success/failure criteria (no way to verify compliance)

Note: "등" after 3+ concrete items (e.g., "Python, Go, Rust 등") is natural Korean enumeration, not a red flag.
