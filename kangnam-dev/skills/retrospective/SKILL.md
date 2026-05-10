---
name: retrospective
description: >
  4L 회고 기법(Liked/Learned/Lacked/Longed For)으로 git 커밋 히스토리와 위키 작성 기록을 분석해
  구조화된 회고를 생성하고 ~/wiki/에 저장하는 스킬. 두 가지 모드: (1) 통합 retro — 기간별,
  여러 프로젝트, 스프린트 retro와 이전 retro의 Action Items를 1차 입력으로 사용, 마지막에 Rule 업데이트 후보 제시.
  (2) 스프린트 retro — 특정 프로젝트의 스프린트 완료 시점, raw git log 직접 분석.
  사용자가 "retro", "회고", "retrospective", "/retrospective", "지난 작업 돌아보자",
  "최근 작업 정리해줘", "이번 주/달 회고 해줘", "스프린트 retro", "스프린트 회고" 등을
  언급할 때 반드시 이 스킬을 사용하세요.
---

**REQUIRED BACKGROUND:** 공통 loop 패턴은 `../_shared/loop-pattern.md` 참조.
이 스킬은 `runner` (회고 본문 생성) → `critic` (채점) 두 helper를 메인 모델이 orchestrate
하는 specialization. 본문 작성과 검증을 분리해 burst 패턴(한 번 흐름으로 끝까지)과
자기합리화 톤을 자동으로 차단한다.

# Retrospective Skill

회고는 **4L 기법** 사용. 카테고리 정의(Liked/Learned/Lacked/Longed For)와 구분 기준은 항상
`~/wiki/Concepts/4L-Retrospective.md`를 읽어 적용. 정의를 이 스킬·helper에 인라인하지 않음 — 단일 출처 유지.

두 가지 모드:
- **통합 retro**: 기간 기반 → `~/wiki/Retro/regular/`
- **스프린트 retro**: 특정 프로젝트의 스프린트 완료 → `~/wiki/Projects/<프로젝트>/Sprints/<버전>/review.md` (또는 `/kangnam-dev:sprint-review` 커맨드 사용)

모드가 불분명하면 사용자에게 질문.

## 구조

```
retrospective/
├── SKILL.md              ← 이 파일 (메인 모델의 orchestration script)
└── agents/
    ├── runner.md         ← 회고 본문 작성 helper (leaf)
    └── critic.md         ← 채점 helper (leaf)
```

`runner.md`와 `critic.md`는 정식 글로벌 subagent가 아니라 _스킬 내부 instruction 파일_이다.
메인 모델이 Read로 본문을 로드한 뒤 `general-purpose` agent의 prompt로 전달하여 실행한다.
글로벌 agent namespace를 오염시키지 않으면서 NEVER #10 (subagent leaf-only) 자연 충족.

---

## Step 1 · 위키 pull + 4L 정의 로드 (메인 모델 직접)

### Step 1-pre · wiki working tree clean 체크 (2026-05-03 추가)

`pull --rebase` 호출 _전에_ wiki가 깨끗한지 확인한다 — unstaged 변경이 있으면 rebase 자체가
실패하고, `git stash`로 우회하다 다른 stash를 잘못 pop해 BOARD.md merge conflict를 만들 수 있다.
실제 사례: auto_company 0.0.4 retro 진입 시 stale `Kanban/InProgress/lunawave-v004-...md`
deletion이 unstaged였고 `git stash pop`이 무관한 WIP를 풀어 BOARD.md 충돌 → 수동 해소 필요.

```bash
status=$(git -C ~/wiki status --porcelain)
if [ -n "$status" ]; then
  # STOP. dirty wiki는 사용자 의사결정 필요.
  # → 변경의 출처(이전 세션 잔재 / 다른 클라이언트 sync 대기 / 의도적 WIP)를 짧게 보고하고
  #   commit · stash · 무시 셋 중 하나를 묻는다. 자동으로 stash pop 하지 않는다.
fi
```

dirty면 메인 모델이 사용자에게 한 줄 요약 + 처리 방안 1~2개 제시 후 응답을 기다린다.
(README/메모성 변경처럼 자명하면 "이 변경 commit하고 진행할까요?" 식으로 좁혀 묻는다.)

### Step 1 · pull + 정의 로드

```bash
git -C ~/wiki pull --rebase
```

`~/wiki/Concepts/4L-Retrospective.md`를 Read. 본문을 변수 `fourL_definitions`로 보관 —
이후 runner/critic 호출 시 prompt에 그대로 포함시킨다.

---

## Step 2 · 모드 결정 (메인 모델 직접)

사용자 발화로 모드를 판정. 모호하면 1회 질문:
> "통합 retro(기간 기반, 여러 프로젝트)와 스프린트 retro(특정 프로젝트의 버전/기능 완료) 중 어느 쪽인가요?"

---

## Step 3 · 데이터 수집 (메인 모델 직접)

helper에 분석을 통째 위임하지 않는다. 메인이 _수집된 데이터_를 prompt로 넘긴다.
이렇게 분리하는 이유: helper의 역할은 _4L 본문 작성_과 _채점_에만 집중. 데이터 수집은
도구 호출이 많아 helper에 맡기면 prompt 비용이 비대해진다.

### 통합 retro (mode = `integrated`)

기간 결정:
```bash
ls ~/wiki/Retro/regular/ 2>/dev/null | sort | tail -1
```
- 사용자 명시 기간 우선. 미명시 시 마지막 통합 retro 이후 ~ 오늘. 없으면 최근 2주.

데이터 3종 수집:

**3-A. 기간 내 스프린트 retro 본문 (1차 입력)**
```bash
git -C ~/wiki log --since="<start_date>" --diff-filter=A --name-only --pretty=format: \
  | grep -E '^Projects/[^/]+/Sprints/[^/]+/review\.md$' | sort -u
```
나온 파일들 모두 Read → `prior_sprint_reviews` 변수에 묶음.

**3-B. 직전 통합 retro의 Action Items + 처리 여부 (1차 입력)**
```bash
ls ~/wiki/Retro/regular/ | sort | tail -2
```
직전 파일의 `## Action Items` 섹션 Read. 각 항목의 처리 여부를 git log로 확인:
```bash
git -C ~/wiki log --since="<직전 retro 날짜>" --oneline --no-merges
```
처리/미처리를 항목별로 라벨링한 결과를 `prior_integrated_retro_actions` 변수에.

**3-C. 스프린트 retro 미커버 영역의 raw git log (보조 입력)**
```bash
git -C ~/wiki log --since="<start_date>" --oneline --no-merges
git log --since="<start_date>" --oneline --no-merges    # 활성 프로젝트 각각
git -C ~/wiki log --since="<start_date>" --name-only --pretty=format: | sort -u | grep '\.md$'
```
의미 있는 변경된 wiki `.md`는 직접 Read해서 _요약본_을 `raw_git_log` 변수에.

### 스프린트 retro (mode = `sprint``)

사용자에게 확인 (1회, 3개 항목):
- 프로젝트명·경로
- 스프린트 라벨 (예: `v0.0.4 — 청산 스프린트`)
- 시작 commit/날짜 (or 명시 기간)

데이터:
```bash
git -C <project_path> log --since="<start_date>" --oneline --no-merges
git -C <project_path> diff <start_commit>..HEAD --stat
```
결과를 `project_git_log` 변수에. 해당 프로젝트의 wiki 문서가 있으면 함께 Read해서 `changed_wiki_docs`에.

---

## Step 4 · runner 호출 (라운드 1)

`agents/runner.md` 본문을 Read. `general-purpose` agent를 spawn하되 prompt 구조:

```
[runner.md 본문 그대로]

---

## This invocation

- mode: <integrated | sprint>
- period: <start_date> ~ <end_date>
- project_name: <…>          # 스프린트 모드만
- sprint_label: <…>        # 스프린트 모드만
- round: 1

### data_bundle
<수집된 데이터 묶음 — 3-A/3-B/3-C 또는 project_git_log/changed_wiki_docs>

### fourL_definitions
<~/wiki/Concepts/4L-Retrospective.md 본문 그대로>
```

응답을 `current_draft`로 보관.

---

## Step 5 · 초안 사전 게이트 (메인 모델 직접)

critic 호출 전 자명한 결함 필터. 하나라도 해당하면 critic 건너뛰고 즉시 REJECT 처리,
runner를 라운드 +1로 재호출:

- 본문 비어 있음
- 4L 4개 섹션 중 누락 (모드별 필수 섹션 기준)
- 항목이 모두 합쳐 5개 이하
- 명백한 합리화 표현 정확 매칭 (runner.md NEVER 목록 중 1건이라도 그대로 포함)

REJECT 사유를 `pre_gate_reject_reason`에 담아 다음 라운드 runner prompt의 `critic_feedback`
자리에 그대로 전달.

---

## Step 6 · critic 호출

`agents/critic.md` 본문을 Read. `general-purpose` agent를 spawn하되 prompt 구조:

```
[critic.md 본문 그대로]

---

## This invocation

- mode: <integrated | sprint>
- round: <N>

### draft
<current_draft 그대로>

### previous_draft        # 라운드 2+만
<직전 라운드 draft>

### previous_critic_output # 라운드 2+만
<직전 라운드 critic JSON>

### fourL_definitions
<~/wiki/Concepts/4L-Retrospective.md 본문 그대로>
```

응답은 JSON. 파싱 실패 시 1회 재호출. 두 번째도 실패면 사용자에게 보고하고 루프 종료.

### 라운드 보고 포맷 (사용자에게)
```
[라운드 N] 점수: X.XX | 결과: PASS/REJECT | 피드백: (1줄 요약)
```

---

## Step 7 · 결과 처리

- **PASS** (총점 > 8.00 AND 합리화 부재 ≥ 8): Step 8로 진행
- **REJECT**:
  - round < 3 → critic feedback을 다음 라운드 runner prompt의 `critic_feedback` 자리에 채워 Step 4 재실행 (round +1)
  - round == 3 → 루프 종료. 3 라운드 중 _가장 높은 총점_을 받은 draft + 모든 라운드 점수를
    사용자에게 보고하고 판단 요청. 사용자가 "그대로 저장"하라고 하면 Step 8 진행, 아니면 종료.

### 무변경 검사
critic이 자동 REJECT(무변경 재제출)을 반환하면 그 라운드의 점수는 _직전 라운드 그대로_ 간주.
runner에 _직전 critic feedback을 그대로 재인용_하여 Step 4 재실행. round 카운터는 증가.

---

## Step 8 · 저장 및 커밋 (메인 모델 직접)

`/kangnam-dev:sprint-review`에서 `output_path`를 받아 호출된 경우에는 예외적으로 이 스킬이
커밋하지 않는다. `output_path`의 기존 scaffold를 채우고 frontmatter `status`를 `evergreen`으로
바꾼 뒤 반환한다. 커밋은 sprint-review command의 Step 5가 담당한다.

```bash
mkdir -p ~/wiki/Retro/regular                              # 통합
mkdir -p ~/wiki/Projects/<프로젝트>/Sprints/<버전>       # 스프린트
```

파일명:
- 통합: `~/wiki/Retro/regular/YYYY-MM-DD.md` (종료 날짜)
- 스프린트: `~/wiki/Projects/<프로젝트>/Sprints/<버전>/review.md`

통합 retro 또는 standalone 스프린트 retro 커밋:
```bash
git -C ~/wiki add Retro/regular/YYYY-MM-DD.md     # 또는 Projects/<프로젝트>/Sprints/<버전>/review.md
git -C ~/wiki commit -m "retro: <start_date> ~ <end_date>"     # 또는 retro(sprint): ...
```

`Rules/`는 add 안 함 (Rule 업데이트 제안은 사용자 승인 후 별도 작업). push 안 함.

출력: 저장 경로 + 통과 라운드 / 최종 점수 + Rule 업데이트 제안 개수.

---

## NEVER 규칙

1. NEVER: runner 또는 critic이 다른 subagent를 호출하도록 prompt 작성하지 마라. 두 helper는 leaf.
2. NEVER: 사전 게이트(Step 5)를 건너뛰고 critic을 호출하지 마라.
3. NEVER: critic의 PASS/REJECT 판정을 메인 모델이 임의로 뒤집지 마라.
   단, _총점이 8.00 이하인데 PASS_ 또는 _합리화 부재 < 8인데 PASS_ 인 경우 채점 오류로 보고 REJECT 처리.
4. NEVER: 4L 정의를 SKILL.md / runner.md / critic.md 어디에도 인라인하지 마라. 항상 `~/wiki/Concepts/4L-Retrospective.md`만 출처.
5. NEVER: `~/wiki/Rules/` 파일을 직접 수정하지 마라. 회고는 _후보_만 제시.
6. NEVER: 데이터 수집(Step 3)을 helper에 위임하지 마라. helper는 본문 작성·채점에만 집중.

## 제한

- **최대 라운드: 3.** 초과 시 최선 draft + 점수 보고 후 사용자 판단.
- **사전 게이트 REJECT도 라운드에 포함.**

## 엣지 케이스

| 상황 | 처리 |
|------|------|
| runner가 비응답/에러 | 1회 재시도. 재시도 실패 시 "회고 본문 생성 실패" 보고 후 종료 |
| critic JSON 파싱 실패 | 1회 재호출. 재호출도 실패 시 현재 draft 사용자 전달 + "수동 검토 필요" |
| critic이 PASS 판정했으나 총점 8.00 이하 또는 합리화 부재 < 8 | 채점 오류로 보고 REJECT 처리, 같은 라운드 critic 재호출 |
| runner가 직전과 본문 동일 (무변경 재제출) | critic의 자동 REJECT 사용. round +1, 직전 feedback 재전달 |
| 사용자가 루프 도중 중단 요청 | 즉시 중단. 현재까지 최선 draft 전달 |
| 3 라운드 모두 REJECT | 최선 draft + 모든 점수 보고 → 사용자가 "저장" 명시하면 Step 8, 아니면 종료 |
| 통합 retro에서 스프린트 retro도, 직전 통합 retro도 없음 (첫 회고) | data_bundle에 raw git log만 채워 runner 호출. critic은 동일 기준 적용 |
