---
description: "스프린트 구현. Kanban 카드별 gate/domain 라벨에 따라 구현 에이전트 dispatch → gate-verifier가 검증 + progress.md + 카드 갱신. 순차 기본, --parallel 병렬."
argument-hint: "<project> <version> [--parallel] [--gates G1,G2,...] [--working-dir <path>]"
disable-model-invocation: true
---

Raw slash-command arguments:
`$ARGUMENTS`

# sprint-implement

`<plugin-root>`는 이 plugin의 `kangnam-dev/` 디렉토리다. 체크아웃에서 실행하면 `/Users/kangnam/projects/kangnam-plugins/kangnam-dev`, 설치본에서 실행하면 설치된 plugin의 `kangnam-dev` 루트로 해석한다.

planning에서 발행된 **Kanban 카드**를 하나씩 구현한다. 각 카드는 planning.md의 Core Gate(`gate: G1` 등)에 연결돼 있어야 하며, 구현은 카드 단위로 진행하고 검증은 gate-verifier가 progress.md와 카드 상태에 기록한다.

## 절차

### Step 0 · 인자 검증

`<project>`와 `<version>`이 모두 있어야 함. 없으면 사용자에게 묻고 종료:

> 어떤 프로젝트의 어떤 스프린트를 구현할까요? 예: `lunawave 0.0.8`

옵션:
- `--parallel` — 게이트 의존성 없으면 병렬 dispatch (default: 순차)
- `--gates G1,G3` — 특정 게이트만 구현 (default: 미완료 게이트 전부)
- `--working-dir <path>` — 코드 디렉토리. default: `~/projects/<project>`

### Step 1 · planning.md / progress.md 로드

```bash
PLAN=~/wiki/Projects/<project>/Sprints/<version>/planning.md
PROG=~/wiki/Projects/<project>/Sprints/<version>/progress.md
uv run <plugin-root>/scripts/sprint/sprint-implement.py $ARGUMENTS --json
```

- planning.md 없음 → "먼저 `/kangnam-dev:sprint-planning <project> <version>` 실행" 안내 후 종료.
- progress.md 없음 → `sprint-implement.py`가 `sprint-progress.py <project> <version>`를 호출해 스캐폴드 생성.

### Step 2 · 게이트 인벤토리

`sprint-implement.py` JSON 출력의 `dispatch` / `incomplete` / `skipped_done`을 기준으로 각 카드+게이트의 필드 추출:

```
card:
  id: 260509-1420
  title: [0.0.8 G1] POST /todos 동작 검증
gate_id: G1
heading: POST /todos 동작 검증
domain: backend
scenarios:
  happy: { description, verify }
  isolation_failure: { description, verify }
  expected_reaction: { description, verify }
```

다음 중 하나라도 빠지면 **incomplete**로 분류 — orchestrator는 그 게이트를 dispatch하지 않고 사용자에게 보고:

- `domain` 필드 없거나 6개 enum 외
- 시나리오 중 하나 이상 description/verify 비어있음
- 게이트 heading이 placeholder 상태
- 게이트에 매칭되는 Kanban 카드 없음
- 하나의 게이트에 Kanban 카드가 2장 이상 매칭됨

`card_only`(sprint 라벨은 있지만 `gate`가 없는 카드)나 `orphan_gate_cards`(planning.md에 없는 gate를 가리키는 카드)가 있으면 dispatch 전에 사용자에게 보고한다. 기본 처리: planning/card 정합성을 먼저 고치고 재실행.

### Step 3 · 미완료 게이트 추려내기

각 게이트가 progress.md에서 다음 상태 중 어느 것인지 `sprint-implement.py`가 판단:

- **done** — 세 시나리오 모두 `- [x]` + 메모(placeholder/manual_pending 아님)
- **partial** — 일부만 `[x]`
- **pending** — 전부 `[ ]`

기본 동작: `pending` + `partial`인 게이트만 dispatch. `done`은 skip.
`--gates G1,G3` 지정 시 그 ID 중 done이 아닌 것만.

### Step 4 · 의존성 분석 (지금은 단순 순차)

기본은 게이트 ID 순서(G1 → G2 → G3)대로 **순차** dispatch.

`--parallel` 지정 시 모든 게이트를 한 번에 병렬 dispatch — 단, 사용자가 게이트 간 의존성을 직접 보장한 것으로 간주(orchestrator는 의존성 검사 안 함).

> **TODO(future)**: planning.md에 게이트별 `depends:` 필드 추가하면 자동 의존성 그래프 가능.

### Step 5 · 게이트별 dispatch

각 게이트마다 두 단계:

#### 5a. 도메인 에이전트 호출 (코드 작성)

게이트 `domain` 필드 → 매핑된 에이전트 호출:

| domain | subagent_type |
|---|---|
| frontend | frontend-dev |
| backend | backend-dev |
| mobile | mobile-dev |
| data | data-engineer |
| devops | devops |
| ai | ai-engineer |

```
Agent(
  subagent_type: <mapped agent>,
  prompt: <below>
)
```

prompt 템플릿:

```
You are <domain>-dev. Implement ONE kanban card of a sprint.

Sprint:
  project: <project>
  version: <version>
  working_directory: <working-dir, absolute>

Card to implement:
  id: <card_id>
  title: <card_title>
  path: <card_path>

Gate linked to this card: <gate_id> — <heading>
  domain: <domain>
  happy:
    description: <text>
    verification: <command or "manual">
  isolation_failure:
    description: <text>
    verification: <command or "manual">
  expected_reaction:
    description: <text>
    verification: <command or "manual">

Goal of the sprint (한 줄 요약):
  <text from planning.md>

Your task:
1. Implement the card so all three linked gate scenarios behave as defined.
2. If a verification value is a test command (pytest/playwright/etc),
   create the referenced test file with the right name and a real assertion.
   Never write `pass`-only tests.
3. Commit with messages tagged `[<gate_id>.happy]`, `[<gate_id>.isolation]`,
   `[<gate_id>.reaction]` as the corresponding scenario becomes implemented.
   One commit may carry multiple tags.
4. Do NOT run the verification commands yourself. gate-verifier does that next.
5. Do NOT edit ~/wiki/ card/progress files. Stay inside <working_directory>. gate-verifier will update progress.md and move the card.

Report on completion:
  status: ready_for_verification | incomplete
  commits: [<short-hash> <subject>, ...]
  files_changed: [<path>, ...]
  blockers: <list of things you couldn't do — empty if none>
```

에이전트가 `incomplete`로 보고하면 사용자에게 그대로 전달하고 그 게이트의 verifier 호출 skip.

#### 5b. gate-verifier 호출 (검증 + 기록)

도메인 에이전트가 `ready_for_verification`로 보고하면:

```
Agent(
  subagent_type: gate-verifier,
  prompt: <below>
)
```

prompt 템플릿:

```
Verify gate <gate_id> of sprint.

project: <project>
version: <version>
gate_id: <gate_id>
working_dir: <working-dir, absolute>
planning_path: <abs path to planning.md>
progress_path: <abs path to progress.md>

Read your instructions in gate-verifier.md and execute.
```

verifier 결과 캡처:
- `passed` — 진행 보고에 ✅ 추가
- `partial` — 사용자에게 어떤 시나리오가 막혔는지 보고
- `failed` — 사용자에게 실패 출력 + 어떤 commit을 봐야 하는지 보고
- `incomplete` — 게이트 정의가 잘못됨, planning.md 수정 필요 (사용자에게 안내)

### Step 6 · 한 게이트 완료 시 사용자 진행 보고

각 게이트 끝날 때마다 한 줄:

```
✓ [260509-1420] G1 (backend, passed) — backend-dev 3 commits, verifier all green, 카드 Done
⚠️ [260509-1430] G2 (frontend, partial) — happy 통과, isolation 명령 실패 (자세히 보려면 progress.md)
✗ [260509-1440] G3 (mobile, incomplete) — mobile-dev 보고: simulator 부팅 실패
```

### Step 7 · 전체 완료 시 요약

```
=== sprint-implement 완료 ===
프로젝트: <project>  스프린트: <version>
게이트: 3개 중
  ✅ passed: 2
  ⚠️ partial: 0
  ❌ failed/incomplete: 1
다음 액션:
  - G3 mobile-dev 차단 사항 해결 후 재실행
  - 또는: /kangnam-dev:sprint-progress <project> <version> 으로 현재 상태 확인
```

`git -C ~/wiki commit` 자동 실행 X — progress.md 변경분은 verifier가 이미 박았으므로 사용자가 검토 후 직접 commit.

## NEVER 규칙

1. NEVER: planning.md 게이트 정의 또는 Kanban 카드 매핑이 incomplete인 채로 도메인 에이전트 dispatch.
2. NEVER: 도메인 에이전트가 `incomplete` 보고하면 verifier 호출 (검증 의미 없음).
3. NEVER: verifier가 `failed` 보고한 게이트의 카드를 강제 Done으로 옮김.
4. NEVER: 6개 enum 외의 domain 값을 임의로 매핑 (예: `fullstack` → backend로 추측). 사용자에게 planning.md 수정 안내.
5. NEVER: 사용자 working-dir 외부에서 도메인 에이전트가 작업하도록 허용. prompt에 명시.
6. NEVER: `--parallel` 시에도 같은 도메인 에이전트를 동시에 두 번 띄우지 않음 (예: G1.backend와 G2.backend는 순차).
7. NEVER: subagent에서 또 다른 subagent 호출 (NEVER #8 규칙). 메인이 모든 dispatch 책임.
8. NEVER: planning.md 자체를 수정. 게이트 정의가 잘못되면 사용자에게 안내, 직접 안 고침.

## ALWAYS 규칙

1. ALWAYS: 카드 dispatch 전에 그 카드의 gate가 progress.md에서 done인지 확인 (idempotent — 재실행해도 done은 skip).
2. ALWAYS: 도메인 에이전트 prompt에 카드 정보 + 게이트의 5개 필드 모두 풀어 전달 (요약 X).
3. ALWAYS: gate-verifier prompt에 working_dir, planning_path, progress_path를 절대 경로로 전달.
4. ALWAYS: 한 게이트 끝날 때마다 한 줄 진행 보고. 무음 X.
5. ALWAYS: 전체 끝나면 요약 + 다음 액션 제안.
6. ALWAYS: `--parallel` 사용 시 사용자에게 명시적으로 "병렬 dispatch — 의존성 직접 책임" 한 번 경고.
