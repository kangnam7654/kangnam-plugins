---
description: "스프린트 시작. 기존 Kanban 카드 intake + 스캐폴드 → 보드 정리 → sprint-planner가 범위/gate/card 매핑 작성 → critic → PASS 시 카드 연결/발행 + commit."
argument-hint: "<project> <version> [--scale micro|standard|major] [--no-auto-archive] [한 줄 목표]"
---

Raw slash-command arguments:
`$ARGUMENTS`

# sprint-planning

`<plugin-root>`는 이 plugin의 `kangnam-dev/` 디렉토리다. 체크아웃에서 실행하면 `/Users/kangnam/projects/kangnam-plugins/kangnam-dev`, 설치본에서 실행하면 설치된 plugin의 `kangnam-dev` 루트로 해석한다.

새 스프린트의 시작점. 6단계 파이프라인:

1. **스크립트** — 안전한 스캐폴드 (frontmatter, 섹션, carry-over 추출, 기존 Kanban intake 카드 목록 삽입)
2. **kanban-curator 에이전트** — 미배정/고아 카드 분석 후 사용자에게 알림 + 안전한 것은 자동 close
3. **sprint-planner 에이전트** — 본문 채움 (모호하면 사용자에게 묻고, fallback 금지)
4. **critic 에이전트 (sprint-plan 모드)** — 5축 채점, PASS = total > 8.0 AND Gate Triple Integrity >= 8
5. **REJECT 루프** — 피드백 들고 sprint-planner에게 다시. 최대 3 라운드. 그래도 REJECT면 사용자에게 보고.
6. **PASS 시** — Kanban epic 발행 + 기존 카드 sprint/gate 연결 + 새 gate 카드 발행 + commit (push X)

## Step 0 · 인자 검증

`$ARGUMENTS`가 비었거나 `<project>`만 있으면 — `<version>`이 없는 상태 — 즉시 사용자에게 묻고 실행하지 마라. 예시:

> 어떤 프로젝트의 어떤 버전 스프린트를 시작할까요? 예: `lunawave 0.0.8` 또는 `dear-jeongbin v0.1.0 --scale micro 'todo CRUD'`

## Step 1 · pull + 스캐폴드

```bash
git -C ~/wiki pull --rebase
uv run <plugin-root>/scripts/sprint/sprint-planning.py $ARGUMENTS
```

스크립트가 처리:
- 프로젝트 폴더 존재 확인
- 버전 SemVer 검증 + v-prefix 컨벤션 자동 적용
- 직전 스프린트 review.md에서 Action Items carry-over 추출
- 현재 프로젝트의 열린 Kanban 카드(Backlog/InProgress/Blocked)를 `Sprint Intake Cards` 섹션에 삽입
- `Sprints/<version>/planning.md` 스캐폴드 (이미 있으면 거부 — `--force`로 덮어쓰기)
- frontmatter에 `scale: <micro|standard|major>` 기록 (critic이 사용)
- `git add` (커밋은 Step 6)

스크립트 stdout에서 다음 정보 캡처:
- 스캐폴드된 `planning.md` 절대 경로
- 직전 스프린트 경로 (있으면) 및 carry-over 개수
- 사용자가 인자로 준 goal 문자열

## Step 1.5 · kanban-curator 에이전트 호출 (보드 점검)

새 스프린트 시작은 칸반 보드의 누적 카드를 정리하는 자연스러운 시점. 스크립트가 이미 현재 프로젝트의 열린 카드를 `Sprint Intake Cards`에 넣어두며, curator는 그 외 미배정 카드 + 옛 스프린트 고아 카드를 **내용 기반**으로 분류한다.

```
Agent(
  subagent_type: "kanban-curator",
  prompt: "
    current_sprint: <Step 1에서 normalize된 version>
    previous_sprint: <Step 1 출력에 표시된 직전 스프린트, 없으면 null>
    current_project: <project>
    working_dir: <프로젝트 작업 디렉터리>
    kanban_data_path: <working_dir>/.kanban/kanban-data.json

    Read kanban-curator.md instructions. Scan project-local cards from kanban_data_path (unassigned + old-sprint orphans, excluding previous_sprint and future-labeled). Classify each as notify / auto_archive_safe / silent. Return YAML output.
  "
)
```

curator의 YAML 출력 파싱:

### `notify` 카드 (있으면)

사용자에게 그대로 표시:

```
🔍 주목해야 할 카드 N장:

  [ID] 제목
    프로젝트: <project> · sprint: <sprint or "(미배정)"> · <N>일 전 · <column>
    이유: <curator의 reason>
    추천: <recommended_action>

  ...

이 중 어떻게 할까요?
  - 'a' 입력: 모두 현재 스프린트(<current_sprint>)로 라벨링
  - 'i' 입력: 개별로 결정 (한 장씩 진행)
  - 's' 입력: 모두 그대로 둠 (skip)
```

`a`: 각 notify 카드에 대해 `<plugin-root>/scripts/agent-kanban/agent-kanban.sh set <id> --cwd <working_dir> --project <project> --sprint <current_sprint>` 일괄 실행한 뒤 planning.md의 `Sprint Intake Cards`에 카드가 보이도록 planner에게 전달.
`i`: 각 카드마다 사용자에게 묻고 처리 (label / close / skip). label이면 current_sprint에 묶고 planner가 gate `card:`로 매핑하게 한다.
`s`: 통과.

### `auto_archive_safe` 카드 (있으면)

curator가 이미 "안전" 판단했으므로 **자동 close(Done 이동) 후 사후 보고**. project-local agent-kanban에는 별도 Archive 컬럼이 없으므로 파일 삭제나 숨김 이동을 하지 않는다:

```
🗂  자동 close: M장 (curator 판단)
  - [ID] 제목 — 이유: <reason>
  - ...

각 카드에 대해 `<plugin-root>/scripts/agent-kanban/agent-kanban.sh done <id> --cwd <working_dir> --summary "sprint planning curator closed stale/non-actionable card"` 실행.
```

단, 사용자가 명령 호출 시 `--no-auto-archive` 인자를 줬다면 Done 이동 대신 사용자 컨펌으로 전환.

### `silent` 카드

표시 안 함. 보고에서 카운트만 ("그 외 N장은 그대로 둠").

### Step 1.5 종료 후 사용자 한 줄 요약

```
보드 정리 완료: notify N장 처리 / auto_close M장 / silent S장. 다음 단계로 진행.
```

## Step 2 · sprint-planner 에이전트 호출

```
Agent(
  subagent_type: "sprint-planner",
  prompt: "<below>"
)
```

prompt 템플릿:
```
Inputs:
  planning_path: <Step 1에서 캡처한 절대 경로>
  project: <project>
  version: <normalized version>
  scale: <micro|standard|major>
  goal: <user-supplied goal, 비어있으면 빈 문자열>
  prev_review_path: <직전 스프린트 review.md 절대 경로 또는 null>

Read sprint-planner.md instructions. Fill in planning.md per its rules.
Important: Use Sprint Intake Cards. Every listed task card must either become a Core Gate with `card: <id>` or be explicitly deferred in Out-of-scope. Every listed epic must either be split into concrete `card: new` gates with `source_epic: <id>` or be explicitly deferred. New work uses `card: new` and `source_epic: none`.
Return the structured report.
```

에이전트는 모호한 부분을 `AskUserQuestion`으로 묶어서 묻는다. 너(orchestrator)는 에이전트가 끝날 때까지 대기.

에이전트 보고가 `incomplete`면 — Step 5로 가지 말고 사용자에게 그대로 전달:

> sprint-planner가 채우지 못한 부분: <agent의 notes>. 어떻게 진행할까요?

## Step 3 · critic 에이전트 (sprint-plan 모드) 호출

```
Agent(
  subagent_type: "critic",
  prompt: "Mode: sprint-plan. Read <planning_path>. Score per rubric-sprint-plan.md. Output PASS/REJECT scorecard."
)
```

critic은 자동으로 sprint-plan 모드를 잡는다 (frontmatter `type: project_spec` + `sprint:` 필드).

critic 결과 캡처:
- `result`: PASS or REJECT
- `total_score`: X.XX
- `feedback`: REJECT일 경우 최대 3개 항목

## Step 4 · REJECT 루프 (최대 3 라운드)

`result == REJECT`이면:

```
Agent(
  subagent_type: "sprint-planner",
  prompt: "<원래 prompt> + 추가:
    Critic feedback (round <N>):
    <critic의 feedback 블록 그대로>
    
    Apply the feedback. Do NOT re-ask the user about questions you already answered.
    Edit planning.md and report."
)
```

그 후 다시 critic 호출. 라운드 카운트 추적.

3 라운드 후에도 REJECT면:
- planning.md는 유지 (덮어쓰지 않음)
- 사용자에게 critic의 마지막 scorecard + feedback 그대로 보고
- "3 라운드 시도했지만 PASS 미달. 직접 검토 후 결정해주세요."
- Step 5로 가지 마라

## Step 5 · Kanban 카드 발행 (PASS 시)

PASS이면 사용자에게 한 줄 확인:

> 점수 X.XX/10.00로 PASS. Kanban 카드 연결/발행할까요? (epic 1장 + 기존 intake 카드 gate 연결 + 새 gate 카드 발행 + 직전 스프린트 열린 카드 보고) (yes/no)

`yes`이면 단일 스크립트 호출:

```bash
uv run <plugin-root>/scripts/sprint/sprint-publish-cards.py <project> <version>
```

스크립트가 한 번에 처리:
- epic 카드 1장 발행 (`type: epic`, project-local `.kanban`의 `sprint` 메타데이터)
- planning.md의 Core Gate `card: <id>`는 기존 task 카드를 `project/sprint/gate`에 자동 연결
- planning.md의 Core Gate `card: new` 또는 비어있는 레거시 gate는 새 task 카드 발행 (`gate: G1` 등 메타데이터)
- `source_epic: <id>`가 있으면 새 task 카드를 해당 기존 epic의 child로 묶고, 없으면 sprint epic에 묶음
- epic 카드를 `card: <id>`로 직접 구현 대상으로 쓰면 거부하고 작은 gate로 쪼개라고 안내
- 직전 스프린트(N-1)에 아직 열린 카드가 남아 있으면 보고. 자동 relabel은 `card:` 매핑으로만 수행

idempotent: 이미 같은 sprint+gate 카드가 있으면 skip. `card: <id>` 매핑은 같은 카드에 metadata를 재적용하므로 재실행해도 중복 발행 안 됨.

세부 제어 플래그 (필요 시):
- `--no-epic` epic만 빼고
- `--no-gate-cards` 게이트별 카드 빼고
- `--no-carryover` 직전 스프린트 열린 카드 보고 생략
- `--legacy-carryover` 예전 방식처럼 직전 스프린트 미완료 카드를 모두 새 sprint로 relabel (권장 X; gate 매핑 없이 `card_only`가 생길 수 있음)

`no`이면 다음 단계로.

## Step 6 · commit

```bash
git -C ~/wiki commit -m "sprint(<project>): <version> planning"
```

push 안 함.

## NEVER 규칙

1. NEVER: Step 0 인자 검증 없이 스크립트 호출하지 마라.
2. NEVER: critic의 REJECT를 무시하고 commit하지 마라.
3. NEVER: 3 라운드 후에도 REJECT인데 강제 PASS 처리하지 마라 — 사용자 결정.
4. NEVER: `git push` 자동 실행하지 마라.
5. NEVER: sprint-planner의 `incomplete` 보고를 무시하고 critic 단계로 넘어가지 마라.
6. NEVER: kanban-curator의 `notify` 결과를 사용자에게 표시하지 않고 다음 단계로 넘어가지 마라.
7. NEVER: kanban-curator가 분류하지 않은 카드를 임의로 close 처리하지 마라.
8. NEVER: `--no-auto-archive` 플래그가 있으면 auto_archive_safe를 자동 처리하지 마라 — 사용자 컨펌.
9. NEVER: Sprint Intake Cards에 있는 기존 카드를 gate 또는 Out-of-scope 없이 암묵적으로 방치하지 마라.
10. NEVER: 하나의 Kanban 카드 id를 두 개 이상의 Core Gate에 매핑하지 마라.
11. NEVER: epic 카드를 `card: <id>`로 직접 매핑하지 마라. epic은 `source_epic`으로만 사용하고 작은 task gate로 쪼갠다.

## ALWAYS 규칙

1. ALWAYS: 스크립트 → curator → sprint-planner → critic → (loop) → epic + commit 순서.
2. ALWAYS: critic의 scorecard를 사용자에게 보여줘 (PASS여도 PASS여도 점수 가시화).
3. ALWAYS: REJECT 라운드마다 critic feedback을 sprint-planner에게 그대로 전달.
4. ALWAYS: Kanban epic 발행은 사용자 확인 후.
5. ALWAYS: curator의 auto_archive_safe 처리 후 사후 보고 (몇 장을 Done으로 이동했는지 명시).
6. ALWAYS: curator의 silent 카드는 카운트만 표시 (개별 표시 X).
7. ALWAYS: planning.md의 `card:` 매핑이 publish 이후 실제 project-local Kanban 메타데이터 `sprint`/`gate`로 반영되는지 확인.
8. ALWAYS: 자유 입력으로 생성된 broad/ambiguous 카드는 epic + `needs-breakdown`으로 남기고, sprint planning에서 작은 gate로 분해.
