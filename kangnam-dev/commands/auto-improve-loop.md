---
description: "Continuous improvement pipeline that runs auto-improve in multiple rounds until a target quality score is reached. Each round runs full Audit→Design→Build→Verify, remembering previous results and reprioritizing."
argument-hint: "[--target-score <n>] [--max-rounds <n>] [<auto-improve flags>] <codebase path>"
---

Raw slash-command arguments:
`$ARGUMENTS`

**REQUIRED BACKGROUND:** 공통 loop 패턴은 `kangnam-dev/skills/_shared/loop-pattern.md` 참조. 이 스킬은 해당 패턴의 specialization이다.
<!-- Override: Ralph Loop pattern — max rounds configurable (default 5), exit conditions differ (score target + stagnation + regression detection); state persisted via improve-progress.yaml across sessions -->

# auto-improve-loop

코드베이스를 목표 품질에 도달할 때까지 자율적으로 반복 개선하는 파이프라인.

Ralph Loop 패턴을 적용한다: 매 라운드마다 fresh context에서 시작하되, `improve-progress.yaml`로 상태를 이어받아 이전에 개선한 영역을 건너뛰고 다음 우선순위로 이동한다.

## 핵심 개념

```
┌─────────────────────────────────────────────────┐
│                auto-improve-loop                 │
│                                                  │
│  Round 1: auto-improve (Full 36단계)             │
│    → improve-progress.yaml 업데이트              │
│    → 종료 조건 평가                                │
│                                                  │
│  Round 2: auto-improve (이전 결과 참조)           │
│    → improve-progress.yaml 업데이트              │
│    → 종료 조건 평가                                │
│                                                  │
│  Round N: ...                                    │
│    → 종료 조건 충족 → 최종 보고                    │
└─────────────────────────────────────────────────┘
```

## Scope

**IN-SCOPE**:
- 기존 코드베이스의 반복적/점진적 개선
- 한 번에 모든 문제를 해결하기 어려운 대규모 코드베이스
- 목표 품질 수준까지 자동으로 도달하길 원하는 경우

**OUT-OF-SCOPE**: auto-improve와 동일 (신규 개발 → auto-dev, 단순 버그 → 직접 수정, 인프라 → 별도)

## 입력

- 코드베이스 경로 (필수)
- 목표 점수 (선택, 기본값: 8.0)
- 최대 라운드 (선택, 기본값: 5)
- 플래그 (선택): auto-improve와 동일한 플래그를 매 라운드에 패스스루 전달
  - 영역 선택: `--code`, `--security`, `--arch`, `--db`, `--test`, `--repo`, `--ui`
  - 확장: `--bm`, `--design`

## 산출물

- `improve-progress.yaml` — 라운드별 누적 진행 상황
- 각 라운드의 auto-improve 산출물 (audit-report, design-spec, build-summary, completion.yaml)
- `improvement-final-report.md` — 전체 루프 종료 시 최종 보고

---

## improve-progress.yaml 구조

Ralph의 progress.txt + prd.json 역할을 하는 단일 파일. 라운드 간 상태 전달의 유일한 매체다.

```yaml
# auto-improve-loop 진행 상태
target_score: 8.0
max_rounds: 5
flags: []  # auto-improve에 전달할 플래그 목록 (예: [--bm, --security])

rounds:
  - round: 1
    timestamp: "2026-03-25T10:00:00"
    status: completed  # completed / failed / skipped
    baseline_scores:
      code_quality: 5.5
      security: 4.0
      architecture: 6.0
      db: 7.5
      test_coverage: 3.0
      repo_health: 5.0
      ux_ui: 6.0
    final_scores:
      code_quality: 6.5
      security: 6.0
      architecture: 6.5
      db: 7.5
      test_coverage: 5.0
      repo_health: 6.0
      ux_ui: 6.5
    items_addressed:
      - id: "SEC-001"
        title: "SQL injection in user search"
        area: security
        priority: P0
      - id: "TEST-001"
        title: "No integration tests for payment flow"
        area: test
        priority: P1
    items_remaining:
      - id: "ARCH-001"
        title: "Circular dependency in core modules"
        area: architecture
        priority: P1
      - id: "CODE-001"
        title: "Inconsistent error handling"
        area: code_quality
        priority: P2
    learnings: |
      - payment 모듈 테스트 추가 시 mock DB 필요
      - security fix로 user search API 시그니처 변경됨

  - round: 2
    # ... 다음 라운드

# 현재 상태 요약 (매 라운드 종료 시 갱신)
current_round: 2
overall_status: in_progress  # in_progress / completed / stopped
latest_scores:
  code_quality: 6.5
  security: 6.0
  architecture: 6.5
  db: 7.5
  test_coverage: 5.0
  repo_health: 6.0
  ux_ui: 6.5
remaining_p0_p1: 1
all_scores_above_target: false
```

저장 경로: `{project}/docs/llm/improve-progress.yaml`

---

## 워크플로우

### 라운드 시작 전: 상태 로드

1. `improve-progress.yaml`이 존재하는지 확인
   - **존재**: 읽어서 현재 라운드 번호, 이전 결과, 남은 항목 파악
   - **미존재**: 라운드 1로 초기화. 사용자 입력(목표 점수, 최대 라운드, 집중 영역)으로 파일 생성

2. 종료 조건 사전 체크
   - 이미 종료 조건 충족 시 → 최종 보고 생성 후 종료
   - 최대 라운드 도달 시 → 최종 보고 생성 후 종료

### 라운드 N 실행

**auto-improve 스킬**을 호출한다. 이전 라운드 컨텍스트를 함께 전달한다.

#### 라운드 1 (초회)

표준 auto-improve를 그대로 실행한다. 추가 컨텍스트 없음.

```
auto-improve를 실행하라.
코드베이스 경로: {project_path}
플래그: {flags}
```

#### 라운드 2+ (반복)

이전 라운드의 결과를 auto-improve에 전달하여 중복 작업을 방지한다. 플래그는 매 라운드 동일하게 전달한다.

```
auto-improve를 실행하라.
코드베이스 경로: {project_path}
플래그: {flags}

[이전 라운드 컨텍스트]
improve-progress.yaml 경로: {progress_yaml_path}

이 파일을 읽고 아래 규칙을 적용하라:
1. Audit Phase: 이전 라운드에서 이미 해결된 항목(items_addressed)은 재진단하지 마라.
   대신 해당 영역의 회귀 여부만 확인하라.
2. Audit Phase: 이전 라운드의 items_remaining을 우선 진단 대상으로 삼아라.
   새로 발견된 항목도 포함하되, 기존 remaining 항목이 우선순위가 높다.
3. Design Phase: 이전 라운드의 learnings를 참고하여 동일한 시행착오를 반복하지 마라.
4. Build Phase: 이전 라운드에서 수정한 코드에 대한 회귀 테스트를 포함하라.
5. Verify Phase: 이전 라운드 final_scores와 현재 라운드 final_scores를 비교하여
   점수가 하락한 영역이 있으면 반드시 보고하라.
```

### 라운드 종료: 상태 업데이트

auto-improve 완료 후, completion.yaml에서 결과를 추출하여 `improve-progress.yaml`을 업데이트한다.

1. 현재 라운드 결과를 `rounds` 배열에 추가
2. `current_round` 증가
3. `latest_scores` 갱신
4. `remaining_p0_p1` 재계산
5. `all_scores_above_target` 재평가
6. git commit (진행 상태 보존)

### 종료 조건 평가

라운드 종료 후 아래 조건을 순서대로 평가한다. 하나라도 충족 시 루프 종료.

| 조건 | 판정 | 비고 |
|------|------|------|
| 모든 영역 점수 >= target_score | **목표 달성** | 성공 종료 |
| current_round >= max_rounds | **라운드 소진** | 부분 성공 종료 |
| 직전 2라운드 연속 점수 변화 없음 (±0.5 이내) | **정체 감지** | 더 돌려도 개선 없음 |
| 직전 라운드 대비 전체 평균 점수 하락 | **회귀 감지** | 경고 후 종료 |

종료 시 → 최종 보고 생성

### 최종 보고: improvement-final-report.md

루프 종료 시 전체 라운드를 종합한 최종 보고를 생성한다.

**doc-loop 스킬**을 자동(B) 모드 + LLM 모드로 호출한다.

**필수 섹션**:

| 섹션 | 내용 |
|------|------|
| 요약 | 총 라운드 수, 종료 사유, 최종 상태 1문장 |
| 점수 추이 | 라운드별 영역별 점수 테이블 (Round 1 → Round N) |
| 개선 항목 전체 목록 | 라운드별로 해결한 항목 (ID, 제목, 영역, 해결 라운드) |
| 미해결 항목 | 남아있는 항목 (있는 경우) + 미해결 사유 |
| 회귀 이력 | 점수가 하락했다가 복구된 영역 (있는 경우) |
| 라운드별 교훈 | 각 라운드의 learnings 통합 |
| 권장 다음 단계 | 추가 개선이 필요한 경우 권장 조치 |

저장 경로: `{project}/docs/llm/improvement-final-report.md`

---

## 중단 및 재개

컨텍스트 윈도우 초과, 세션 종료 등으로 루프가 중단될 수 있다. `improve-progress.yaml`이 파일로 영속화되어 있으므로:

1. 새 세션에서 `auto-improve-loop`를 다시 호출
2. `improve-progress.yaml`을 읽어서 마지막 완료된 라운드 이후부터 재개
3. 중단된 라운드(status가 없거나 incomplete)는 처음부터 재실행

이것이 Ralph Loop의 핵심 — fresh context에서 시작하되 파일 기반 상태로 연속성을 보장한다.

---

## Circuit Breaker

무한 루프나 비생산적 반복을 방지하는 안전장치.

| 조건 | 동작 |
|------|------|
| 동일 항목이 3라운드 연속 items_remaining에 존재 | 해당 항목을 "해결 불가"로 표기, 나머지 항목으로 계속 |
| auto-improve 실행 중 Phase 게이트 FAIL 2회 연속 | 해당 라운드를 failed로 기록, 다음 라운드로 진행 |
| 전체 평균 점수가 3라운드 연속 하락 | 루프 강제 종료 + 사용자 보고 |

---

## 스킬 계층

```
auto-improve-loop (이 스킬)
  └── auto-improve (매 라운드마다 호출)
        ├── audit-loop (#1~#9)
        ├── design-loop (#10~#26)
        ├── build-loop (#27~#31)
        └── verify-loop (#32~#36)
```

auto-improve-loop는 auto-improve의 상위 오케스트레이터다. 라운드 관리, 상태 영속화, 종료 조건 평가만 수행하고, 실제 개선 작업은 전적으로 auto-improve에 위임한다.

---

## NEVER 규칙

1. NEVER: improve-progress.yaml 없이 라운드 2+를 시작하지 마라. 파일이 없으면 라운드 1부터 시작한다.
2. NEVER: 종료 조건을 건너뛰지 마라. 매 라운드 종료 후 반드시 평가한다.
3. NEVER: auto-improve 내부 Phase 순서를 변경하지 마라. 라운드 관리만 이 스킬의 책임이다.
4. NEVER: improve-progress.yaml을 수동 편집하지 마라. 이 스킬의 워크플로우를 통해서만 갱신한다.
5. NEVER: 회귀 감지(점수 하락) 시 경고 없이 계속하지 마라.

## ALWAYS 규칙

1. ALWAYS: 매 라운드 종료 후 improve-progress.yaml을 업데이트하고 git commit하라.
2. ALWAYS: 라운드 2+에서는 이전 라운드 컨텍스트를 auto-improve에 전달하라.
3. ALWAYS: 종료 시 improvement-final-report.md를 생성하라.
4. ALWAYS: 정체 감지(2라운드 연속 변화 없음) 시 루프를 종료하라. 무의미한 반복을 방지한다.
5. ALWAYS: 각 라운드의 learnings를 기록하라. 다음 라운드의 시행착오 방지에 필수적이다.

---

## 경계

- 이 스킬은 **라운드 관리자**다. auto-improve를 반복 호출하고, 상태를 영속화하고, 종료를 판단한다.
- 개선 작업 자체에 개입하지 않는다. Audit, Design, Build, Verify의 세부 사항은 auto-improve와 하위 스킬이 담당한다.
- auto-improve의 동작을 변경하지 않는다. 추가 컨텍스트를 전달하여 행동을 조정할 뿐이다.
- improve-progress.yaml이 라운드 간 유일한 통신 채널이다. 다른 방식으로 상태를 전달하지 마라.
