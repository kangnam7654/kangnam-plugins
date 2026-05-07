# Precision Rules

Every quality attribute MUST be expressed as a measurable target. Zero tolerance for vague qualifiers.

## Banned Words → Required Replacements

| Banned term | Required replacement (example) |
|---|---|
| "efficient" | "O(n log n) or better for collections > 1000 items" or "< 200ms p95 response time" |
| "scalable" | "Handles 10x current load (100 → 1000 concurrent users) without architecture change" |
| "robust" | "Recovers from single-node failure within 30 seconds with zero data loss" |
| "high availability" | "99.9% uptime (< 8.76 hours downtime per year)" |
| "low latency" | "< 50ms p99 for read operations" |
| "maintainable" | "New developer adds a CRUD endpoint in < 2 hours following existing patterns" |
| "secure" | Cite specific controls: "mTLS for inter-service calls; secrets in Vault, rotated every 90 days" |
| "clean architecture" | "3-layer separation (handler → service → repository) with no import from handler into repository" |
| "적절히" | Specify the exact threshold or method |
| "필요에 따라" | List the exact conditions that trigger the action |
| "기타" | List all items explicitly |

## Rule

If you cannot quantify a quality attribute because requirements are missing, write:
```
[TBD: requires <specific information> from user to quantify]
```

Do NOT invent a number. Mark it TBD with the specific information needed.

## Default Targets by Project Category

When targets are unspecified, propose these defaults and label them `[PROPOSED — confirm or override]`:

| Category | Latency p95 | Uptime | Concurrent users |
|---|---|---|---|
| Internal tool | < 500ms | 99% | < 100 |
| Consumer web app | < 200ms | 99.9% | < 10k |
| High-traffic API | < 50ms | 99.99% | < 100k |
