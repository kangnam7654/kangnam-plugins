# HUMAN Mode Scoring Rubric

Each criterion scored **0–10**. Integer scores only (no half points, no decimals).

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
| 1 | **Readability** | 30% | (a) Average sentence length <= 25 words. (b) >= 80% of instruction sentences use active voice. (c) Every jargon term is defined on first use or linked to a glossary. (d) A developer with 1 year of professional experience can follow the document without external references. |
| 2 | **Structure** | 25% | (a) Heading hierarchy is sequential (no skipped levels, e.g., H1 → H3). (b) Document follows progressive disclosure: overview → details → edge cases. (c) Each section is self-contained (reading one section does not require reading a prior section for basic comprehension). (d) Every heading describes the content that follows (not generic headings like "Notes" or "Misc"). |
| 3 | **Examples** | 20% | (a) Every non-trivial concept (any concept that cannot be understood from a single sentence) has a code example or concrete illustration. (b) Code examples are copy-paste runnable without modification. (c) Expected output is shown for every code example. (d) Examples use realistic data, not placeholder values like "foo" or "test123". |
| 4 | **Completeness** | 15% | (a) Covers the full lifecycle: prerequisites → installation → configuration → usage → troubleshooting. (b) All prerequisites are listed with version numbers. (c) No implicit steps (every action the reader must take is explicitly stated). (d) At least 3 common error scenarios and their solutions are documented. |
| 5 | **Accuracy** | 10% | (a) All CLI commands execute without error on the stated platform. (b) All file paths reference files that exist in the repository. (c) API signatures match the actual code. (d) No information that was true in a previous version but is now outdated. |

## Score Calculation

```
Total = (Readability × 0.30) + (Structure × 0.25) + (Examples × 0.20)
      + (Completeness × 0.15) + (Accuracy × 0.10)
```

**Primary criterion**: Readability. PASS requires Readability >= 8.

## Red Flags (auto cap Readability at 5)

If ANY of these are present, Readability cannot exceed 7:
- Any paragraph longer than 5 sentences without a visual break (blank line, bullet list, or code block)
- Any jargon term used before being defined (first occurrence must include a definition)
- "Simply", "just", or "easily" appearing before a step that requires more than 1 command or action
- Passive voice used for instructions the reader must perform (e.g., "should be run" instead of "run")
