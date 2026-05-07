# API Design Review Checklist (#14)

## Scoring Criteria

| Criterion | Weight | Score 0-10 | What to evaluate |
|---|---|---|---|
| **RESTfulness** | 0.25 | | Correct HTTP methods (GET=read, POST=create, PUT=update, DELETE=delete). Resource-based URLs. No verbs in paths. Proper status codes. |
| **Consistency** | 0.25 | | Naming convention uniform across all endpoints. Response structure uniform. Pagination format uniform. Error format matches tech-stack standard. |
| **Auth coverage** | 0.20 | | Every endpoint has explicit `auth_required` field. Public endpoints justified. Admin-only endpoints use role-based access. No auth bypass paths. |
| **Error handling** | 0.15 | | Error response schema defined. Distinct error codes for client vs server errors. Validation errors return field-level detail. Rate limiting documented. |
| **Completeness** | 0.15 | | Every CRUD operation for every entity has an endpoint. List endpoints have pagination. Bulk operations where UX demands (batch create/delete). |

## PASS Condition

- Total > 8.0 (weighted average)
- Primary criterion (RESTfulness or Consistency, both weight 0.25) >= 7
- If both score 0.25: primary is the lower-scoring one (stricter gate)

## Common FAIL Reasons

| Issue | Feedback template |
|---|---|
| Verb in URL path | "POST /api/v1/createUser → POST /api/v1/users 로 변경. REST 규칙: URL에 동사 금지." |
| Inconsistent naming | "일부 엔드포인트는 camelCase, 일부는 snake_case. tech-stack에서 정한 {convention}으로 통일." |
| Missing auth on sensitive endpoint | "{method} {path}에 auth_required가 false이나, {entity} 데이터에 접근함. 인증 필수." |
| No pagination on list endpoint | "GET {path}는 목록 조회이나 pagination 파라미터 없음. limit/offset 또는 cursor 추가." |
| Missing error schema | "{method} {path}의 error response schema 미정의. tech-stack 에러 포맷에 맞춰 정의." |
