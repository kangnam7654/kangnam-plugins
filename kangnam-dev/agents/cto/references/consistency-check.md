# DB-API Consistency Check (#15)

## Purpose

Cross-validate that the DB schema (#11) and API design (#13) are aligned. Every API endpoint must have a corresponding DB operation, and every significant DB table must be accessible through the API.

## Scoring Criteria

| Criterion | Weight | Score 0-10 | What to evaluate |
|---|---|---|---|
| **Endpoint-Table mapping** | 0.30 | | Every CRUD API endpoint maps to a specific DB table/view. No endpoint references a non-existent table. No orphan tables (tables with no API access and no internal-only justification). |
| **Field coverage** | 0.25 | | API request/response fields match DB column names and types. No type mismatches (e.g., API says string but DB column is integer). Nullable fields in DB are optional in API. |
| **Relationship integrity** | 0.25 | | API endpoints that return nested resources match DB foreign key relationships. Join paths are valid. N+1 query risks identified for nested endpoints. |
| **Auth-RLS alignment** | 0.20 | | Endpoints with `auth_required: true` access tables with RLS policies. Public endpoints only access tables without row-level restrictions. No auth bypass through alternative endpoints. |

## PASS Condition

- Total > 8.0 (weighted average)
- Primary criterion (Endpoint-Table mapping, weight 0.30) >= 7

## Mismatch Classification

When FAIL, classify the root cause:

| Classification | Condition | next_step |
|---|---|---|
| `SCHEMA_MISMATCH` | API references tables/columns that don't exist in schema, OR schema has tables that API cannot reach without justification | #11 (DB schema revision) |
| `ENDPOINT_MISMATCH` | Schema is correct but API endpoints don't cover required operations, OR API response fields don't match DB types | #13 (API design revision) |
| `BOTH` | Issues exist on both sides | #11 first (resolve schema), then #13 sequentially |

## Common FAIL Reasons

| Issue | Classification | Feedback template |
|---|---|---|
| API references non-existent table | SCHEMA_MISMATCH | "엔드포인트 {method} {path}가 테이블 {table}을 참조하나, DB 스키마에 해당 테이블 없음." |
| DB table has no API access | ENDPOINT_MISMATCH | "테이블 {table}에 대한 API 엔드포인트 없음. 내부 전용이면 주석으로 명시, 아니면 엔드포인트 추가." |
| Type mismatch | ENDPOINT_MISMATCH | "API 응답 필드 {field}은 string이나 DB 컬럼 {table}.{column}은 integer. 타입 통일." |
| Auth-RLS misalignment | BOTH | "엔드포인트 {path}는 인증 불필요(auth_required: false)이나, 테이블 {table}에 RLS 정책 있음. 접근 불가." |
