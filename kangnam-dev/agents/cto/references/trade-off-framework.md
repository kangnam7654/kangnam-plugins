# Trade-Off Framework

Every technology decision with 2+ options MUST use this scoring framework.

## Scoring Dimensions (1-5)

| Dimension | 1 (worst) | 3 (acceptable) | 5 (best) |
|---|---|---|---|
| **Complexity** | 3+ new technologies the team has never used | 1 new technology or significant refactor | Existing stack only, minimal new concepts |
| **Performance** | Exceeds latency/throughput budget by > 2x | Meets budget with < 20% headroom | Meets budget with > 50% headroom |
| **Maintainability** | New developer needs > 1 week to understand the subsystem | 1-3 days | < 1 day |
| **Time-to-implement** | > 4 weeks for a single developer | 1-4 weeks | < 1 week |
| **Durability** | Requires rearchitecture at 2x current scale | Handles up to 5x current scale | Handles 10x+ current scale without change |

## Default Weights

- Complexity: 20%
- Performance: 25%
- Maintainability: 25%
- Time-to-implement: 15%
- Durability: 15%

Adjust weights per project. State the reason for any change.

## Weighted Total Calculation

```
total = (complexity × 0.20) + (performance × 0.25) + (maintainability × 0.25) + (time × 0.15) + (durability × 0.15)
```

## Decision Rules

- **Clear winner**: Highest total, difference > 0.3 → recommend that option.
- **Close call**: Two options within 0.3 of each other → present both with tiebreaker rationale. Tiebreaker priority: Maintainability > Performance > Durability > Time > Complexity.
- **All below 2.5**: No option is acceptable → propose a fundamentally different approach or escalate to user.

## Output Format

```
### Decision: [What is being decided]

| Criterion (weight) | Option A: [name] | Option B: [name] |
|---|---|---|
| Complexity (20%) | [1-5] — [1-sentence justification] | [1-5] — [justification] |
| Performance (25%) | [score] — [justification] | [score] — [justification] |
| Maintainability (25%) | [score] — [justification] | [score] — [justification] |
| Time-to-implement (15%) | [score] — [justification] | [score] — [justification] |
| Durability (15%) | [score] — [justification] | [score] — [justification] |
| **Weighted total** | **X.XX** | **X.XX** |

**Recommendation**: [Option]. [1-2 sentence rationale tied to scores].
```
