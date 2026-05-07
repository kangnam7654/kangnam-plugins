---
name: service-dev
description: "서비스 개발의 전체 라이프사이클을 오케스트레이션하는 스킬. 아이디어 → 설계 → UX 리서치 → 비주얼 디자인(선택) → 스펙 → 구현 → 문서화까지 7단계를 순차 진행하며, 각 단계마다 품질 게이트를 통과해야 다음으로 넘어간다. '서비스 만들어', '앱 개발하자', '프로젝트 시작하자', 'build a service', 'develop an app', '아이디어 있는데 개발해줘', '서비스 개발', '새 프로젝트 셋업'의 요청에 트리거. idea-forge로 아이디어를 이미 검증한 경우에도 이 스킬을 사용하여 구현까지 진행한다. 단순 코드 수정이나 버그 픽스에는 사용하지 않는다. 처음부터 서비스를 만드는 작업에만 사용할 것."
---

# service-dev

서비스 개발의 전체 라이프사이클을 7개 Phase로 나누어 진행한다. 각 Phase는 기존 에이전트/스킬을 호출하고, Phase 내부의 품질 루프(Critic 루프)는 글로벌 CLAUDE.md 오케스트레이션에 위임한다. 이 스킬은 **Phase 간 전환 조건과 산출물 전달**만 정의한다.

## 범위

### IN SCOPE
- 새로운 서비스/앱/프로젝트를 처음부터 만드는 작업
- idea-forge로 검증된 아이디어를 구현까지 이어가는 작업
- 7개 Phase(Ideate → Plan → UX Research → Visual Design → Spec → Build → Document) 전체 또는 중간 Phase부터 재개

### NEVER
1. NEVER: 기존 서비스의 버그 수정, 단순 코드 수정, 기능 추가에 이 스킬을 사용하지 마라. 해당 작업은 일반 코딩 워크플로우를 따른다.
2. NEVER: 사용자 승인 없이 Phase를 건너뛰거나 다음 Phase로 진행하지 마라. Phase 3(Visual Design)만 유일한 optional Phase이며, 건너뛸 때에도 사용자 확인이 필요하다.
3. NEVER: Phase 5(Build)에서 spec.md에 정의되지 않은 기능을 구현하지 마라. 추가 기능이 필요하면 Phase 4로 돌아가 spec.md를 갱신한다.
4. NEVER: Phase 간 산출물을 `docs/{service-name}/` 외부에 저장하지 마라.
5. NEVER: Phase 5에서 테스트 없이 다음 모듈로 진행하지 마라. 각 모듈의 Step 4(test) 완료가 필수다.

## Phase 개요

```
Phase 0: Ideate         → 아이디어 확보
Phase 1: Plan           → 아키텍처 설계 + 구현 계획
Phase 2: UX Research    → 페르소나 + 저니맵 + IA + 유저 플로우 (필수)
  ├ 2a: 페르소나 + 저니맵 (→ Phase 1 피드백 루프)
  └ 2b: IA + 유저 플로우
Phase 3: Visual Design  → Wireframe + Hi-fi (optional, Figma 필요)
  ├ 3a: Wireframe
  └ 3b: Hi-fi Design
Phase 4: Spec           → AI용 개발 스펙 문서
Phase 5: Build          → 모듈별 [dev→review→refactor→test] 사이클
Phase 6: Document       → 사람용 문서 (README, API 문서, 배포 가이드)
```

## 시작 시 확인 사항

스킬 시작 시 사용자에게 아래를 확인한다:

1. **아이디어 소스**: idea-forge 산출물이 있는가, 직접 아이디어를 제공할 것인가?
2. **비주얼 디자인 필요 여부**: UI가 필요한 서비스인가? (Phase 3 실행 여부 결정. Phase 2 UX Research는 모든 서비스에 필수.)
3. **서비스 이름**: 산출물 저장 경로에 사용할 이름 (`docs/{service-name}/`)

---

## Phase 0: Ideate

**목표**: 서비스 아이디어를 확보하고 구조화한다.

**경로 A** — idea-forge 사용:
- `/idea-forge` 스킬을 호출하여 아이디어 발굴/검증/BM 설계까지 수행한다.
- idea-forge 완료 후 산출물을 추출한다.

**경로 B** — 사용자 직접 입력:
- 사용자가 제공한 아이디어를 아래 4가지 항목으로 정리한다.

**산출물** (4가지 필수):

```
서비스 개요: {한 문장으로 서비스 설명}
핵심 기능: {번호 매긴 기능 목록, 3~7개}
타겟 사용자: {구체적 페르소나, 규모/직군/고충 포함}
BM 요약: {무료/유료 구분, 가격, 핵심 유료 기능}
```

**게이트**: 사용자가 위 4가지 산출물을 확인하고 승인하면 Phase 1로 진행한다.

---

## Phase 1: Plan

**목표**: 아키텍처를 설계하고 구현 계획을 수립한다.

Planner → Plan-Critic 루프를 실행한다 (글로벌 CLAUDE.md 오케스트레이션). Phase 0 산출물을 Planner의 컨텍스트로 전달한다.

**Planner에게 전달할 지시**:
- 아키텍처 설계 (컴포넌트 간 관계, Mermaid 다이어그램 포함)
- 기술 스택 선정 (선정 이유 포함)
- 모듈 분해 (모듈별 책임 1줄 정의)
- 구현 순서 (의존성 기반 정렬)
- DB 스키마 (ERD, 테이블 정의, 인덱스) — DB가 필요한 서비스만

**산출물 저장**: `docs/{service-name}/design.md`, `docs/{service-name}/architecture.mmd` + `.png`

**게이트**: Plan-Critic PASS + 사용자 승인 → Phase 2로 진행한다.

---

## Phase 2: UX Research (필수)

**목표**: 사용자 중심으로 서비스의 구조와 흐름을 설계한다. CLI, API, 웹, 앱 등 사용자가 존재하는 모든 서비스에 필수다.

designer 에이전트를 호출하여 2개 Sub-Phase를 순차 진행한다.

**출력 형식**: Figma MCP가 연결되어 있으면 Figma에 시각화한다. 연결되어 있지 않으면 Mermaid 다이어그램 + 마크다운으로 `docs/{service-name}/ux-research.md`에 저장한다.

### Phase 2a: 페르소나 + 저니맵

Phase 0의 타겟 사용자 정보를 designer에게 전달한다:

- **유저 페르소나**: 이름, 역할, 목표, 페인포인트, 행동 패턴. 서비스 특성에 따라 1~3개 페르소나를 생성한다.
- **유저 저니맵**: 핵심 페르소나 기준으로 인지→탐색→결정→사용→재방문 단계별 행동, 감정, 터치포인트, 페인포인트를 정리한다.

**피드백 루프**: UX Research 결과가 Phase 1 아키텍처에 영향을 주는 경우(예: 저니맵에서 발견된 새 터치포인트가 추가 모듈을 요구하는 경우) → 사용자에게 보고하고, 승인 시 Phase 1의 design.md를 갱신한 뒤 2b로 진행한다.

**게이트**: 사용자가 페르소나 + 저니맵을 승인하면 2b로 진행한다.

### Phase 2b: IA + 유저 플로우

Phase 2a의 페르소나/저니맵과 Phase 1의 모듈 분해를 기반으로:

- **정보 구조(IA)**: 사이트맵/메뉴 구조를 트리 형태로 설계. 상위→하위 계층 관계와 네비게이션 패턴을 정의한다.
- **유저 플로우**: 핵심 태스크(예: 회원가입, 결제, 핵심 기능 사용) 경로를 흐름도로 설계. 시작→판단→행동→결과 노드로 구성한다.

이 단계에서 화면/인터페이스 목록이 확정된다. Phase 1에서 도출한 모듈 목록과 대조하여 누락된 화면이 있으면 추가한다.

**게이트**: 사용자가 IA + 유저 플로우를 승인하면 다음으로 진행한다.
- 비주얼 디자인 필요 → Phase 3
- 비주얼 디자인 불필요 → Phase 4

---

## Phase 3: Visual Design (Optional)

**목표**: UI 디자인을 제작한다.

**실행 조건**: UI가 필요한 서비스에서 사용자가 명시적으로 디자인을 요청한 경우에만 실행한다. CLI 도구, 백엔드 API 등 UI가 불필요한 서비스는 건너뛴다. **Stitch MCP 연결이 필수**이다 — 연결되어 있지 않으면 사용자에게 알리고 건너뛴다.

Google Stitch를 사용하여 텍스트 프롬프트 기반으로 UI를 생성한다. Stitch는 디자인 시스템을 자동 생성하고, HTML/CSS 코드를 내보낼 수 있다.

### Phase 3a: Wireframe

Phase 2b에서 확정된 화면 목록을 기반으로:

1. `mcp__stitch__create_project`로 Stitch 프로젝트를 생성한다.
2. 각 화면에 대해 `mcp__stitch__generate_screen_from_text`로 와이어프레임을 생성한다. 프롬프트에 "wireframe style, grayscale, focus on layout and structure" 키워드를 포함한다.
3. 유저 플로우의 핵심 경로 순서대로 화면을 생성하여, 사용자가 흐름을 따라가며 검토할 수 있게 한다.
4. 생성된 화면은 `mcp__stitch__get_screen`으로 스크린샷과 HTML을 확인한다.

**디바이스 타입 선택**: 서비스 유형에 따라 `deviceType` 파라미터를 설정한다.
- 웹앱 → `DESKTOP`
- 모바일 앱 → `MOBILE`
- 태블릿 → `TABLET`
- 반응형 → 주요 플랫폼 1개 선택 후 `generate_variants`로 다른 디바이스 변형 생성

**게이트**: 사용자가 와이어프레임을 승인하면 3b로 진행한다.

### Phase 3b: Hi-fi Design

Phase 3a 와이어프레임을 하이파이로 변환한다:

1. `mcp__stitch__edit_screens`로 기존 와이어프레임에 색상, 타이포그래피, 아이콘을 적용한다. 프롬프트에 브랜드 색상, 스타일 방향을 구체적으로 명시한다.
2. `mcp__stitch__generate_variants`로 디자인 변형을 생성하여 사용자에게 선택지를 제공한다 (`creativeRange: "EXPLORE"`, `variantCount: 3`).
3. Stitch가 자동 생성하는 디자인 시스템(색상 팔레트, 타이포그래피, 컴포넌트 규칙)을 `docs/{service-name}/design-system.md`에 저장한다.

**게이트**: 사용자가 최종 디자인을 승인하면 Phase 4로 진행한다.

---

## Phase 4: Spec

**목표**: AI가 개발 시 참조할 스펙 문서를 작성한다.

Writer → Doc-Critic 루프를 실행한다 (글로벌 CLAUDE.md 오케스트레이션, **LLM 모드**). `writer` 에이전트를 사용한다.

**입력**: Phase 1 산출물 + Phase 2 산출물 + Phase 3 산출물(있는 경우)

**스펙 문서에 포함할 항목**:
- 모듈별 요구사항 (각 모듈이 무엇을 해야 하는지)
- API 스키마 (엔드포인트, 요청/응답 형식, 에러 코드)
- 데이터 모델 (엔티티, 관계, 테이블 정의)
- 에러 처리 규칙 (어떤 상황에서 어떤 에러를 반환하는지)
- 코딩 컨벤션 및 제약 조건

**산출물 저장**: `docs/{service-name}/spec.md`

**spec.md 구조 예시** (하나의 모듈):

```markdown
# 개발 스펙: {module-name} 모듈

## 모듈 요구사항
- {요구사항 1}
- {요구사항 2}

## API 스키마
### POST /api/{resource}
요청: { "field": type }
응답 (201): { "id": string, ... }
에러: 400 — {조건}, 403 — {조건}

## 데이터 모델
- {table} 테이블: {columns}

## 에러 처리 규칙
- {상황} 시 {HTTP status}를 반환한다.
```

**게이트**: Doc-Critic PASS (LLM 모드) + 사용자 승인 → Phase 5로 진행한다.

---

## Phase 5: Build

**목표**: 코드를 구현하고 모든 테스트를 통과시킨다.

Phase 1에서 정의한 구현 순서에 따라 모듈별로 아래 사이클을 반복한다.

### 모듈별 사이클

각 모듈에 대해 순서대로 수행한다:

**Step 1: dev** — spec.md를 참조하여 코드를 작성한다. → `git commit`

**Step 2: review** — 프로젝트의 주 언어에 따라 코드 리뷰 에이전트를 선택한다:
- Go → `code-reviewer` 에이전트
- 그 외 언어 → 메인 모델이 아래 체크리스트로 직접 리뷰한다:
  1. **spec 준수**: 각 기능이 spec.md에 정의된 요구사항을 충족하는가
  2. **에러 처리**: spec.md의 에러 처리 규칙이 코드에 반영되었는가
  3. **입력 검증**: 외부 입력(API 파라미터, 사용자 입력)에 대한 검증 로직이 존재하는가
  4. **네이밍/구조**: 함수명과 변수명이 역할을 설명하는가, 단일 함수가 50줄을 초과하지 않는가
  5. **보안**: 하드코딩된 시크릿, SQL 인젝션 가능 쿼리, 미인코딩 사용자 입력 출력이 없는가

피드백을 반영하여 수정한다. → `git commit`

**Step 3: refactor** — 가독성을 높인다. 구체적으로:
- 역할이 불명확한 변수명을 의미 있는 이름으로 변경
- 20줄 이상의 로직 블록을 별도 함수로 추출
- 중복 코드를 공통 함수로 통합

→ `git commit`

**Step 4: test** — Unit 테스트를 작성하고 통과를 확인한다. → `git commit`

모든 단계에서 반드시 git commit을 수행한다. commit 메시지는 `{type}({module}): {description}` 형식을 따른다.

**모듈 사이클 진행 예시**:

```
[dev]      src/todos/router.py, service.py, models.py
           → git commit -m "feat(todos): implement CRUD endpoints"

[review]   리뷰 피드백: status 전이 검증 누락 → 반영
           → git commit -m "fix(todos): add status transition validation"

[refactor] validate_status_transition()을 별도 함수로 추출
           → git commit -m "refactor(todos): extract validation logic"

[test]     tests/unit/test_todos_service.py (15 cases)
           → git commit -m "test(todos): add unit tests for service"
```

### 모든 모듈 완료 후

1. **통합 테스트**: 모듈 간 연동을 검증한다.
2. **E2E 테스트**: qa-engineer 에이전트로 전체 시나리오를 검증한다.
3. **Coverage 확인**: Unit 테스트 커버리지 80% 이상을 달성한다.

**게이트**: 세 가지 검증을 모두 통과하면 Phase 6으로 진행한다.

---

## Phase 6: Document

**목표**: 사람이 읽을 문서를 작성한다.

`writer` → Doc-Critic 루프를 실행한다 (글로벌 CLAUDE.md 오케스트레이션, **HUMAN 모드**).

**작성할 문서**:
- `README.md` — 프로젝트 소개, 사전 준비, 빠른 시작, API 개요, 배포 방법
- 개발 과정 기록 — 각 Phase에서 무엇을 했는지, 주요 결정 사항
- API 문서 — API 엔드포인트가 있는 서비스인 경우 전체 엔드포인트 상세 작성. API가 없으면 생략.
- 배포 가이드 — 서버 배포가 필요한 서비스인 경우 환경별 배포 절차 작성. 로컬 전용이면 생략.

**게이트**: Doc-Critic PASS (HUMAN 모드) → 완료.

---

## Phase 간 전환 조건 요약

| 전환 | 게이트 |
|------|--------|
| 0 → 1 | 사용자가 아이디어 승인 |
| 1 → 2 | Plan-Critic PASS + 사용자 승인 |
| 2a → 2b | 사용자가 페르소나 + 저니맵 승인 (필요 시 Phase 1 design.md 갱신) |
| 2b → 3 | 사용자가 IA + 유저 플로우 승인 + 비주얼 디자인 요청 |
| 2b → 4 | 사용자가 IA + 유저 플로우 승인 + 비주얼 디자인 불필요 |
| 3a → 3b | 사용자가 와이어프레임 승인 |
| 3b → 4 | 사용자가 최종 디자인 승인 |
| 4 → 5 | Doc-Critic PASS (LLM) + 사용자 승인 |
| 5 → 6 | 전체 테스트 통과 + Coverage 80%+ |
| 6 → 완료 | Doc-Critic PASS (HUMAN) |

게이트를 통과하지 못하면 현재 Phase에 머문다. 사용자에게 현재 상태와 미통과 조건을 보고한다.

---

## 산출물 저장 경로

```
{project}/
├── docs/{service-name}/
│   ├── design.md           # Phase 1: 아키텍처 설계
│   ├── architecture.mmd    # Phase 1: 다이어그램 원본
│   ├── architecture.png    # Phase 1: 다이어그램 렌더링
│   ├── ux-research.md      # Phase 2: 페르소나, 저니맵, IA, 유저 플로우
│   └── spec.md             # Phase 4: AI용 개발 스펙
├── README.md               # Phase 6: 프로젝트 소개
├── src/                    # Phase 5: 프로덕션 코드
└── tests/                  # Phase 5: 테스트 코드
```

---

## Edge Case 처리

| 상황 | 대응 |
|------|------|
| idea-forge가 아이디어 검증에 실패 (CSO REJECT 5회) | 사용자에게 보고하고, 아이디어를 직접 제공할지 다른 주제로 재시도할지 판단을 요청한다. |
| Plan-Critic이 5회 연속 REJECT | 현재 플랜과 미해결 피드백을 사용자에게 보고하고 판단을 요청한다. |
| Phase 2a에서 UX Research가 Phase 1 아키텍처 변경을 요구 | 변경 영향 범위를 사용자에게 보고한다. 승인 시 design.md를 갱신하고 2b로 진행한다. |
| Phase 3에서 Stitch MCP 연결 실패 | 사용자에게 "Stitch MCP 설정을 확인해주세요"라고 안내한다. 연결할 수 없으면 Phase 3을 건너뛰고 Phase 4로 진행한다. |
| Phase 5에서 테스트가 반복 실패 | 3회 연속 같은 테스트가 실패하면 사용자에게 보고한다. 사용자가 테스트 수정 또는 스펙 변경을 선택한다. |
| Coverage 80% 미달 | 커버리지가 가장 낮은 모듈 상위 3개를 식별하여 사용자에게 보고한다. 테스트 추가 또는 기준 조정을 사용자가 결정한다. |
| 사용자가 Phase 순서를 건너뛰려 함 | Phase 3(Visual Design)만 건너뛸 수 있다. Phase 2(UX Research)는 필수이며 건너뛸 수 없다. 다른 Phase는 "이전 Phase의 산출물이 필요합니다"라고 안내한다. |
| spec.md에 없는 기능을 구현하라는 요청 | Phase 4로 돌아가 spec.md를 먼저 갱신할 것을 안내한다. |

## 중단 및 재개

사용자가 작업을 중단하고 나중에 돌아올 수 있다. 재개 시:

1. `docs/{service-name}/` 디렉토리를 확인하여 어떤 Phase까지 완료되었는지 판단한다.
2. 완료된 Phase의 산출물을 읽어 컨텍스트를 복원한다.
3. 다음 Phase부터 이어서 진행한다.

**판단 기준**:
- `design.md` 존재 → Phase 1 완료
- `ux-research.md` 존재 → Phase 2 완료
- `spec.md` 존재 → Phase 4 완료
- `src/` 디렉토리에 코드 존재 + 테스트 통과 → Phase 5 완료
- `README.md` 존재 → Phase 6 완료
