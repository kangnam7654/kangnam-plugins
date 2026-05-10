---
description: "Automated diagnosis and improvement pipeline for existing apps. Audits codebase across code quality, security, architecture, DB, tests, UX/UI, then prioritizes and executes design, implementation, and verification."
argument-hint: "[--code|--security|--arch|--db|--test|--repo|--ui] [--bm] [--design] <codebase path>"
---

Raw slash-command arguments:
`$ARGUMENTS`

# auto-improve

"이 서비스 점검해줘" → 종합 진단 → 개선 설계 → 구현 → 검증. 기존 코드베이스를 체계적으로 개선하는 전자동 파이프라인.

4 Phase(Audit → Design → Build → Verify)를 오케스트레이션한다.

## 플래그 동작

### 영역 선택 플래그

`--code`, `--security`, `--arch`, `--db`, `--test`, `--repo`, `--ui` 플래그로 진단 영역을 제한할 수 있다.

| 플래그 사용 | 동작 |
|---|---|
| 플래그 없음 | 기본 7개 영역 전체 진단 (현재와 동일, DB/UI는 자동감지) |
| 특정 플래그만 | 해당 영역만 진단+개선 (나머지 SKIP) |

예: `auto-improve --security --test` → 보안과 테스트만 진단+개선.

### 확장 플래그

`--bm`과 `--design`은 기본 진단에 포함되지 않는 확장 영역이다. 명시적으로 켜야만 실행된다.

- `--bm`: 영역 선택 플래그와 조합 가능. 예: `--security --bm` → 보안 + BM 진단.
- `--design`: `--ui`의 심화 버전. `--design` 사용 시 `--ui`도 자동 포함.
- 영역 선택 플래그 없이 `--bm`만 사용 시: 기본 7개 전체 + BM 추가.

## Scope

**IN-SCOPE**: 아래 조건을 만족하는 요청:
- 기존 코드베이스의 종합 진단 + 개선
- 웹앱, 모바일앱, 백엔드 API, CLI 도구, 라이브러리 모두 포함
- 코드 품질, 보안, 아키텍처, 성능, 테스트, UX/UI 중 하나 이상의 개선

**OUT-OF-SCOPE**: "auto-improve는 기존 코드베이스 진단+개선 전용입니다." 응답 후 종료:
- 신규 앱/서비스 개발 → auto-dev 안내
- 단순 버그 1개 수정 → 직접 수정 안내
- 인프라 배포, CI/CD 설정, 서버 관리
- 문서 작성, 데이터 분석, 비개발 업무

## 스킬 계층

```
auto-improve
  ├── audit-loop (#1~#9)           ← NEW
  │     └── doc-loop (#9)
  ├── design-loop (#10~#26)       ← 재활용
  │     ├── architecture-loop (#10~#16)
  │     │     └── doc-loop (#16)
  │     ├── ux-ui-loop (#17~#22)  ← 조건부
  │     │     └── doc-loop (#22)
  │     ├── plan-loop (#23~#24)
  │     └── doc-loop (#26)
  ├── build-loop (#27~#31)        ← 재활용
  │     └── doc-loop (#31)
  └── verify-loop (#32~#36)       ← 재활용
```

## 워크플로우

```
[사용자 입력: 기존 코드베이스 경로 + 플래그(선택)]
  ↓
Audit Phase: audit-loop (#1~#9, 플래그에 따라 영역 선택)
  ↓ #9 CTO 게이트 PROCEED + audit-report.md 산출
BM 라우팅 (--bm 시에만): BM 없으면 bm-designer로 신규 설계
  ↓
Design Phase: design-loop (#10~#26)
  ↓ #25 CTO 게이트 PASS → design-spec.md 산출
Build Phase: build-loop (#27~#31)
  ↓ → build-summary.md 산출
Verify Phase: verify-loop (#32~#36)
  ↓ #35 릴리즈 디베이트 PASS → completion.yaml 산출
[완성 보고 + Before/After 지표]
```

---

## Phase 1: Audit (#1~#9)

**audit-loop 스킬**을 호출한다. 사용자 입력(코드베이스 경로)과 플래그를 전달한다. 영역 선택 플래그가 있으면 해당 영역만, 없으면 기본 전체 진단. `--bm` 플래그 시 BM 진단도 포함. `--design` 플래그 시 심화 디자인 리뷰도 포함.

audit-loop가 대상 분석(#1), 병렬 진단(#2~#8: 플래그에 따라 선택적), CTO 종합 판정 + Audit Report 문서화(#9)를 수행한다.

**Phase 전환 조건**: #9 CTO 게이트 PROCEED (개선 대상이 존재하고 우선순위 확정)

**게이트 결과 분기**:
- PROCEED → Phase 2로 진행
- SKIP → "진단 결과 개선이 필요한 항목이 없습니다." 보고 후 종료
- PARTIAL → 사용자에게 개선 범위 확인 후 진행

**산출물**: audit-report.md (베이스라인 점수, 우선순위별 개선 항목, 개선 범위)

---

## Phase 1.5: BM 라우팅 (`--bm` 시에만)

`--bm` 플래그가 없으면 이 단계를 SKIP하고 Phase 2로 직행한다.

Audit Phase 완료 후, audit-report.md의 BM 진단 결과를 확인하여 라우팅한다:

| audit BM 결과 | 처리 |
|---|---|
| BM 존재 + 개선 필요 | BM 개선 항목을 design-loop에 전달 (추가 작업 없음) |
| BM 존재 + 양호 | BM 관련 추가 작업 없음 |
| **BM 없음** | **bm-designer 에이전트를 호출하여 BM 신규 설계** |

### BM 신규 설계 (BM 없을 때)

**bm-designer 에이전트**를 호출한다. audit-report.md의 프로젝트 정보를 컨텍스트로 전달:

```
아래 기존 앱/서비스에 대한 BM을 설계하라:

## 제품 정보
- 프로젝트: {audit-report.md의 대상 개요}
- 기술 스택: {tech_stack}
- 주요 기능: {audit에서 파악된 기능 목록}

수익 모델 선택, 가격 티어 설계, 유닛 이코노믹스(3시나리오), BM Score를 산출하라.
```

**산출물**: bm-design.yaml → Design Phase에 audit-report.md와 함께 전달

---

## Phase 2: Design (#10~#26)

**design-loop 스킬**을 호출한다.

### 입력 문서 매핑

design-loop은 원래 idea-brief.md를 입력으로 기대한다. auto-improve에서는 audit-report.md가 이를 대체한다. `--bm`으로 bm-design.yaml이 산출된 경우 함께 전달한다. design-loop 호출 시 아래 컨텍스트를 함께 전달하라:

```
입력 문서: audit-report.md (Audit Phase 산출물)
이 문서는 idea-brief.md를 대체한다.
기존 코드베이스 개선 프로젝트이므로:
- architecture-loop: 기존 아키텍처 기반으로 개선 사항만 설계하라
- ux-ui-loop: audit-report.md에서 UX/UI 개선이 필요한 경우에만 실행하라
- plan-loop: 하위호환성과 마이그레이션 경로를 반드시 포함하라
```

### 조건부 서브-루프 실행

audit-report.md의 개선 우선순위에 따라 design-loop 내부 서브-루프를 선택적으로 실행한다:

| audit 결과 | design-loop 내부 실행 |
|---|---|
| 아키텍처/DB/API 개선 필요 | architecture-loop 실행 |
| UX/UI 개선 필요 | ux-ui-loop 실행 |
| 둘 다 필요 | 둘 다 실행 |
| 코드 품질/보안/테스트만 | architecture-loop 최소 실행 (영향 범위 파악) |

plan-loop와 CTO Design 게이트(#25)는 항상 실행한다.

**Phase 전환 조건**: #25 CTO Design 게이트 PASS

**산출물**: design-spec.md (audit-report + arch-spec + ux-ui-spec 흡수 완료)

---

## Phase 3: Build (#27~#31)

**build-loop 스킬**을 호출한다. 입력: design-spec.md.

build-loop가 구현(#27 병렬), DBA 리뷰(#28), 코드/보안 리뷰(#29), 테스트(#30), Build Summary 문서화(#31)를 수행한다.

### auto-improve 추가 컨텍스트

build-loop 호출 시 아래 컨텍스트를 함께 전달하라:

```
기존 코드베이스 개선 프로젝트이므로:
- #27 구현: 기존 코드를 수정/개선하라. 기존 기능을 깨뜨리지 마라.
- #30 테스트: 기존 테스트가 모두 통과하는지 확인하라 (회귀 테스트).
  새 테스트 추가와 함께, 기존 테스트 스위트 전체 실행이 필수다.
```

**Phase 전환 조건**: 게이트 없음 (Build 내부 리뷰로 충분)

**산출물**: build-summary.md

---

## Phase 4: Verify (#32~#36)

**verify-loop 스킬**을 호출한다. 입력: design-spec.md + build-summary.md.

verify-loop가 동작 검증(#32), UI 검증(#33), 사용성 테스트(#34), C-suite 릴리즈 디베이트(#35), 완성 보고(#36)를 수행한다.

### auto-improve 추가 컨텍스트

verify-loop 호출 시 아래 컨텍스트를 함께 전달하라:

```
기존 코드베이스 개선 프로젝트이므로:
- #32 동작 검증: 개선된 기능 + 기존 기능 모두 동작 확인 (회귀 검증).
- #33 UI 검증: 개선 전/후 비교. audit-report.md의 베이스라인 점수와 비교하라.
- #35 릴리즈 디베이트 (4자: CEO/CTO/CSO/CISO): "론칭"이 아니라 "릴리즈" 관점.
  개선 효과 vs 하위호환 리스크를 중심으로 토론하라.
  CISO는 개선 사항이 보안 정책/컴플라이언스에 영향을 미치는지, 새로운 보안 위험을 도입하지 않는지 검증하라.
- #36 완성 보고: Before/After 지표를 반드시 포함하라.
  audit-report.md의 베이스라인 점수 vs 개선 후 점수를 항목별로 비교.
```

**산출물**: completion.yaml (Before/After 지표 포함)

### completion.yaml 확장 필드

```yaml
# auto-improve 전용 필드
improvement_summary:
  baseline_scores:
    code_quality: <audit 시점 점수>
    security: <audit 시점 점수>
    architecture: <audit 시점 점수>
    test_coverage: <audit 시점 점수>
    ux_ui: <audit 시점 점수 또는 N/A>
    bm: <audit 시점 점수 또는 N/A>        # --bm 시에만
    design: <audit 시점 점수 또는 N/A>    # --design 시에만
  final_scores:
    code_quality: <개선 후 점수>
    security: <개선 후 점수>
    architecture: <개선 후 점수>
    test_coverage: <개선 후 점수>
    ux_ui: <개선 후 점수 또는 N/A>
    bm: <개선 후 점수 또는 N/A>           # --bm 시에만
    design: <개선 후 점수 또는 N/A>       # --design 시에만
  regression_test_result: PASS/FAIL
  total_improvements: <개선된 항목 수>
  total_findings: <진단에서 발견된 총 항목 수>
```

---

## Cross-Phase 복귀 처리

verify-loop가 FAIL을 반환할 때, 복귀 대상이 다른 Phase에 있을 수 있다. auto-improve가 라우팅을 담당한다:

| verify-loop FAIL | 복귀 대상 | auto-improve 처리 |
|---|---|---|
| #32 FAIL → #27 | Build Phase | build-loop 재실행 |
| #32 FAIL → #23 (2회 동일 에러) | Design Phase | design-loop에 plan-loop 재실행 요청 |
| #33 FAIL → #19 | Design Phase | design-loop에 ux-ui-loop 재실행 요청 (UI부터) |
| #34 FAIL → #17 | Design Phase | design-loop에 ux-ui-loop 재실행 요청 (UX부터) |
| #35 코드 수정 → #27 | Build Phase | build-loop 재실행 |
| #35 설계 변경 → 사용자 | Human-in-loop | 사용자에게 보고, 판단 대기 |
| **회귀 실패** → #27 | Build Phase | build-loop 재실행 (회귀 수정 우선) |

Cross-Phase 복귀 시: 복귀 대상 Phase 스킬을 재실행한다. 이전 Phase의 산출물 중 복귀 대상 이전 단계의 산출물은 유지한다.

문서 라이프사이클 주의: Design Phase 재실행 시 design-spec.md가 이미 존재할 수 있다. 재실행된 서브-루프의 산출물로 design-spec.md를 업데이트한다.

### 복귀 반환 포맷

Phase 스킬이 auto-improve에게 복귀를 요청할 때 아래 YAML 구조로 반환한다:

```yaml
phase_return:
  status: "FAIL"
  source_step: "#32"
  source_phase: "verify"
  target_step: "#27"
  target_phase: "build"
  reason: "회귀 실패: 기존 테스트 3건 깨짐"
  attempt: 1
  same_error_consecutive: false
```

auto-improve는 `target_phase`로 라우팅하고, 회귀 실패인 경우 build-loop 재실행 시 회귀 수정 우선 컨텍스트를 전달한다.

---

## NEVER 규칙

1. NEVER: Phase 게이트를 건너뛰지 마라. Audit→Design은 CTO #9 PROCEED 필수, Design→Build는 CTO #25 PASS 필수.
2. NEVER: 에이전트가 다른 에이전트를 직접 호출하지 마라. 모든 에이전트 호출은 해당 Phase의 스킬(오케스트레이터)을 통해서만 수행한다.
3. NEVER: 루프 상한을 초과하여 재시도하지 마라. 각 루프의 상한과 소진 처리는 아래 "루프 소진 처리" 테이블을 따른다.
4. NEVER: SKIP 불가 단계의 실패를 무시하고 다음 단계로 진행하지 마라. SKIP 가능 여부는 아래 "단계 분류" 테이블을 따른다.
5. NEVER: 동일 Phase 내에서 단계 순서를 변경하지 마라. (예외: #2~#8 진단은 병렬 허용, #27 구현은 병렬 허용)
6. NEVER: 기존 기능을 깨뜨리는 변경을 회귀 테스트 없이 통과시키지 마라.

## ALWAYS 규칙

1. ALWAYS: 리뷰/검증 단계에서는 수학적 채점(기준별 0~10 × 가중치 → 총점)으로 PASS/FAIL을 판정한다. PASS: 총점 > 8.0 AND 주요 기준 >= 7.
2. ALWAYS: Phase 전환 시 이전 Phase의 전체 산출물을 다음 Phase에 전달한다.
3. ALWAYS: 실패 복귀 시 복귀 대상 단계의 산출물만 재생성한다. 그 이전 단계의 산출물은 유지한다.
4. ALWAYS: 문서화 단계(#9, #16, #22, #26, #31)는 doc-loop 스킬을 자동(B) 모드 + LLM 모드로 호출한다.
5. ALWAYS: Verify Phase의 완성 보고(#36)에 Before/After 점수 비교를 포함한다.
6. ALWAYS: audit-report.md의 베이스라인 점수를 모든 Phase에 전달하여 개선 효과 측정의 기준점으로 사용한다.

---

## 단계 분류 (SKIP 가능 여부)

| 단계 | SKIP 가능 | 조건 |
|------|----------|------|
| #5 DB 진단 | O | 프로젝트에 DB가 없을 때 |
| #8 UX/UI 진단 | O | 프로젝트에 UI가 없을 때 (CLI, 라이브러리 등) |
| #8-B 동적 진단 | O | 앱 실행 불가 시 (8-A 정적 진단만으로 진행) |
| #28 DBA 리뷰 | O | DB/SQL/마이그레이션 파일이 없을 때 |
| 그 외 모든 단계 | X | FAIL 시 루프 재시도 또는 에스컬레이션 |

## 루프 소진 처리

| 루프 | 상한 | 소진 시 처리 |
|------|------|------------|
| #2~#8 진단 (각각) | 10회 | 해당 영역 "진단 불가" 표기, 나머지로 진행 |
| #9 CTO 판정 | 10회 | 사용자 보고, 수동 판정 요청 |
| #12 DB 스키마 리뷰 | 10회 | CTO 최종 판정 (위험 수용 or ABORT) |
| #14 API 리뷰 | 10회 | CTO 최종 판정 |
| #15 DB-API 정합성 | 10회 | CTO 최종 판정 |
| #18 UX 검증 | 10회 | CTO 판정 |
| #20 UI 검증 | 10회 | CTO 판정 |
| #21 디자인 디베이트 | 10회 (라운드) | CTO 최종 판정 확정 |
| #23-#24 plan-loop | 내부 5회, 외부 10회 | 내부 소진→design-loop에 FAIL 반환. 외부 소진→CTO 게이트(#25) 에스컬레이션 |
| #25 Design 게이트 | 10회 | 사용자 보고: "Design Phase 해결 불가" + 중단 |
| #28 DBA 리뷰 | 10회 | CTO 에스컬레이션 |
| #29 코드/보안 리뷰 | 10회 | CTO 에스컬레이션 |
| #30 테스트 | 10회 | 사용자 보고 + 중단 |
| #32 동작 검증 | 10회 | 사용자 보고 + 중단 |
| #33 UI 패리티 | 10회 | 사용자 보고 + 중단 |
| #34 사용성 테스트 | 10회 | 사용자 보고 + 중단 |
| #35 릴리즈 디베이트 | 10회 (라운드) | 사용자 보고 (human-in-loop 전환) |

---

## 문서 라이프사이클

```
audit-report.md (#9) ──────────────┐
                                    │
arch-spec.md (#16) ────────────────┤
                                    ├→ design-spec.md (#26) 생성 → 3개 삭제
ux-ui-spec.md (#22) ───────────────┤
                                    │
실행계획+CTO승인 ───────────────────┘

design-spec.md (#26) ─────────── Verify Phase까지 유지
build-summary.md (#31) ──────── Verify Phase까지 유지
audit-report.md ─────────────── Verify Phase까지 유지 (Before/After 비교용)
```

Verify Phase 시점 동시 존재 문서: 3개 (audit-report + design-spec + build-summary).

auto-dev와의 차이: audit-report.md가 Verify Phase까지 유지된다. Before/After 점수 비교에 필요하기 때문이다. design-spec.md 생성 시 audit-report.md를 흡수하지 않고 별도 보존한다.

---

## 시스템 실패 처리

| 실패 유형 | 처리 |
|---|---|
| 에이전트 응답 없음/타임아웃 | 3회 재시도 (30초 간격). 3회 실패 시 사용자 보고 후 중단. |
| 도구 호출 실패 | SKIP 가능(#5 DB진단, #8 UX/UI진단): 경고와 함께 진행. SKIP 불가: 사용자 보고 후 중단. |
| 컨텍스트 윈도우 초과 | 현재 Phase 산출물을 파일로 저장하고, 사용자에게 보고. |

---

## 경계

- 이 스킬은 **최상위 오케스트레이터**다. 4개 Phase 스킬(audit-loop, design-loop, build-loop, verify-loop)을 순차 호출하고 Cross-Phase 복귀를 라우팅한다.
- 각 Phase 스킬이 내부 단계를 오케스트레이션한다. auto-improve는 개별 단계(#10, #11, ...)를 직접 관리하지 않는다.
- 에이전트를 직접 호출하지 않는다 — Phase 스킬에게 위임하고, Phase 스킬이 메인 모델에 에이전트 호출을 요청한다.
- design-loop, build-loop, verify-loop은 기존 스킬을 그대로 재활용한다. auto-improve가 추가 컨텍스트(개선 프로젝트 특성, audit-report.md 참조 등)를 전달하여 행동을 조정한다.
