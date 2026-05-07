# DB Schema Review Checklist (#12)

## Scoring Criteria

| Criterion | Weight | Score 0-10 | What to evaluate |
|---|---|---|---|
| **Normalization** | 0.25 | | 3NF minimum. No redundant columns. Junction tables for M:N. Denormalization allowed only with performance justification. |
| **Indexing** | 0.20 | | Primary keys on every table. Foreign key indexes. Composite indexes for frequent query patterns. No over-indexing (< 5 indexes per table for OLTP). |
| **Constraints** | 0.20 | | NOT NULL on required fields. UNIQUE on business keys. CHECK constraints for enums/ranges. FK constraints with correct ON DELETE behavior. |
| **RLS / Security** | 0.15 | | Row-Level Security policies for multi-tenant data. No direct public access to sensitive tables. Service role separation. |
| **Scalability** | 0.20 | | Partition strategy for tables expected to exceed 10M rows. UUID vs serial PK decision documented. Timestamp columns (created_at, updated_at) on every table. |

## PASS Condition

- Total > 8.0 (weighted average)
- Primary criterion (Normalization, weight 0.25) >= 7

## Common FAIL Reasons

| Issue | Feedback template |
|---|---|
| Missing FK index | "테이블 {table}의 FK {column}에 인덱스가 없음. FK 조인 쿼리 성능 저하 예상." |
| No RLS on multi-tenant table | "테이블 {table}에 RLS 정책 없음. tenant_id 기반 행 수준 보안 추가 필요." |
| Redundant column | "{table}.{column}은 {other_table}.{other_column}에서 파생 가능. 정규화 위반." |
| Missing created_at/updated_at | "테이블 {table}에 타임스탬프 컬럼 없음. created_at, updated_at 추가 필요." |
| No partition strategy for large table | "테이블 {table}은 예상 행 수 {N}. 파티션 전략 문서화 필요." |
