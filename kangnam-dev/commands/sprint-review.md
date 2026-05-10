---
description: "스프린트 리뷰/회고. 산출물 리뷰 후 review.md 스캐폴드 + retrospective + Rule 업데이트 후보 처리."
argument-hint: "<project> <version>"
---

Raw slash-command arguments:
`$ARGUMENTS`

# sprint-review

`<plugin-root>`는 이 plugin의 `kangnam-dev/` 디렉토리다. 체크아웃에서 실행하면 `/Users/kangnam/projects/kangnam-plugins/kangnam-dev`, 설치본에서 실행하면 설치된 plugin의 `kangnam-dev` 루트로 해석한다.

스프린트 종료 시점의 리뷰/회고. **Python 스크립트가 progress와 Kanban 카드 완료 상태를 검증하고 review.md 골격을 만들며**, 그 다음 산출물 리뷰와 retrospective 스킬로 4L 본문(Liked/Learned/Lacked/Longed For)을 채운다.

## 절차

### Step 1 · 스캐폴드

```bash
uv run <plugin-root>/scripts/sprint/sprint-review.py $ARGUMENTS
```

스크립트 동작:
- progress.md가 `status: evergreen`인지 확인 (아니면 거부; `--allow-unfrozen`으로 draft 모드)
- 스프린트 Kanban 카드가 존재하고 모두 `Done`인지 확인 (아니면 거부; `--allow-open-cards`로 draft/legacy 모드)
- planning.md `created` ~ progress.md `updated`로 period 자동 계산
- planning.md의 Core Gates 개수 카운트
- Done 카드 목록을 retrospective 컨텍스트에 포함
- review.md 스캐폴드 생성 (4L 섹션 placeholder + Action Items 빈자리)
- retrospective 스킬에 전달할 컨텍스트 묶음 출력

### Step 2 · 산출물 리뷰

retro를 쓰기 전에 다음을 먼저 확인하고 review.md의 “스프린트 개요”에 반영한다:

- planning.md Core Gates가 progress.md에서 모두 검증 완료됐는가
- Done 카드의 구현 산출물이 해당 gate/card 범위와 일치하는가
- 실패/부분 완료/수동 검증/이월 항목이 있으면 retro 전에 명시되어 있는가
- 코드 변경이 있었다면 테스트/빌드/수동 검증 로그가 progress.md에 남아 있는가

산출물 리뷰에서 blocker가 발견되면 retrospective 작성으로 넘어가지 말고, progress/card 상태를 먼저 바로잡는다.

### Step 3 · retrospective 스킬 호출

스크립트 출력에 표시된 컨텍스트를 retrospective 스킬에 전달:

```
mode: sprint
project: <project>
sprint: <version>
period_start: <planning.md created>
period_end: <progress.md updated>
output_path: ~/wiki/Projects/<project>/Sprints/<version>/review.md
context_files:
  - planning.md
  - progress.md
done_cards:
  - [card-id] title (path gate=G1)
```

retrospective 스킬이 `~/wiki/Concepts/4L-Retrospective.md` 정의에 따라 4L 본문 작성 + critic 채점 + 통과까지 반복. PASS 후 review.md frontmatter `status`를 `evergreen`으로 바꾸고 placeholder를 모두 제거한다.

### Step 4 · Rule 업데이트 후보 제시 및 적용

review.md 작성 완료 후 사용자에게:

> Action Items: <N>개 / Rule 업데이트 후보: <N>건 발견
> 적용하시겠습니까? (Rule 변경은 사용자 승인 후 별도 작업)

사용자가 승인하면 같은 세션에서 해당 Rule 파일을 수정한다. Rule 변경은 wiki 규칙이므로 `~/wiki/Rules/MAP.md` 라우팅을 기준으로 대상 파일을 고르고, review.md와 Rule 변경은 커밋을 분리한다.

### Step 5 · 커밋

```bash
git -C ~/wiki add Projects/<project>/Sprints/<version>/review.md
git -C ~/wiki commit -m "retro(sprint): <project> <version>"
```

승인된 Rule 변경이 있으면 별도 커밋:

```bash
git -C ~/wiki add Rules/<file>.md
git -C ~/wiki commit -m "rules: <short lesson>"
```

커밋 전 확인:
- `review.md` frontmatter `status: evergreen`
- Action Items가 placeholder가 아니라 실제 항목
- Rule 업데이트가 승인된 경우 review 커밋과 Rule 커밋이 분리되어 있음

push 안 함.

### Step 6 · 다음 스프린트 안내

```
다음 스프린트 시작:
/kangnam-dev:sprint-planning <project> <next-version>
```

## NEVER 규칙

1. NEVER: progress.md가 evergreen 아닌데 review를 evergreen으로 만들지 마라 (스크립트가 자동으로 draft로 시작).
2. NEVER: 열린 Kanban 카드가 남아 있는데 review를 evergreen으로 만들지 마라.
3. NEVER: 산출물 리뷰 blocker가 남아 있는데 retrospective를 완료 처리하지 마라.
4. NEVER: 4L 카테고리 임의 변형하지 마라 — `~/wiki/Concepts/4L-Retrospective.md` SSOT.
5. NEVER: Action Items가 비어있는 review.md commit하지 마라.
6. NEVER: Rule 업데이트를 사용자 승인 없이 자동 적용하지 마라.

## ALWAYS 규칙

1. ALWAYS: 스크립트로 스캐폴드 → 산출물 리뷰 → retrospective 스킬로 본문 작성 순서.
2. ALWAYS: planning.md + progress.md + Done 카드 목록을 컨텍스트로 retrospective에 전달.
3. ALWAYS: review.md를 `Projects/<project>/Sprints/<version>/review.md`에 저장.
4. ALWAYS: Action Items 섹션 + Rule 업데이트 후보 승인/적용 여부로 마무리.
