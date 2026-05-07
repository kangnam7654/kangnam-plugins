# Design Debate Arbitration Checklist (#21 consensus failure)

## Purpose

When ux-reviewer and ui-reviewer cannot reach consensus, CTO evaluates each conflict point using this checklist.

## Per-Conflict Scoring (0-10 per position)

For each conflict point, score BOTH the ux-reviewer's position and the ui-reviewer's position on these criteria:

| Criterion | Weight | What to evaluate |
|---|---|---|
| **User goal alignment** | 0.35 | Does this position help the primary persona (from idea-brief.md) complete their core task faster or with less friction? |
| **Technical feasibility** | 0.25 | Is this position implementable within the chosen tech stack (from arch-spec.md) without introducing new dependencies or architectural changes? |
| **Design consistency** | 0.20 | Does this position maintain visual and interaction consistency across the app's screen set? |
| **Implementation cost** | 0.20 | How much additional development time does this position require compared to the alternative? (Higher score = less cost) |

## Decision Rules

- **Clear winner**: One position scores > 0.5 higher than the other → select that position.
- **Close call**: Positions within 0.5 of each other → favor the position aligned with the project's primary user persona (from idea-brief.md).
- **Both positions score below 5.0**: Neither position is acceptable → provide a third alternative that addresses both concerns.

## Output Mapping

Map results to the `review-verdict` YAML template:

- `criteria` array: One entry per conflict point.
  - `name`: Description of the conflict (e.g., "Navigation pattern: tab bar vs hamburger menu")
  - `weight`: Equal weight per conflict (1.0 / number of conflicts)
  - `score`: Winning position's weighted score (0-10)
  - `detail`: "[Selected position]. [1-sentence rationale referencing score difference]"

- `feedback` array: Action items for the author of the losing position.
  - Format: "[Agent name]: [Specific revision instruction for the resolved conflict]"

- `verdict`: PASS (arbitration always produces a resolution; there is no FAIL for arbitration).
- `next_step`: 22 (UX-UI Spec 문서화).
