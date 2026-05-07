---
description: "스프린트 회고. review.md 스캐폴드 (스크립트) + retrospective 스킬로 4L 본문 작성."
argument-hint: "<project> <version>"
disable-model-invocation: true
---

Raw slash-command arguments:
`$ARGUMENTS`

# sprint-review

스프린트 종료 시점의 회고. **Python 스크립트가 review.md 골격을 만들고**, retrospective 스킬이 4L 본문(Liked/Learned/Lacked/Longed For)을 채운다.

## 절차

### Step 1 · 스캐폴드

```bash
uv run ~/.claude/plugins/marketplaces/kangnam-local/kangnam-dev/scripts/sprint/sprint-review.py $ARGUMENTS
```

스크립트 동작:
- progress.md가 `status: evergreen`인지 확인 (아니면 거부; `--allow-unfrozen`으로 draft 모드)
- planning.md `created` ~ progress.md `updated`로 period 자동 계산
- planning.md의 Core Gates 개수 카운트
- review.md 스캐폴드 생성 (4L 섹션 placeholder + Action Items 빈자리)
- retrospective 스킬에 전달할 컨텍스트 묶음 출력

### Step 2 · retrospective 스킬 호출

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
```

retrospective 스킬이 `~/wiki/Concepts/4L-Retrospective.md` 정의에 따라 4L 본문 작성 + critic 채점 + 통과까지 반복.

### Step 3 · Rule 업데이트 후보 제시

review.md 작성 완료 후 사용자에게:

> Action Items: <N>개 / Rule 업데이트 후보: <N>건 발견
> 적용하시겠습니까? (Rule 변경은 사용자 승인 후 별도 작업)

### Step 4 · 커밋

```bash
git -C ~/wiki commit -m "retro(sprint): <project> <version>"
```

push 안 함.

### Step 5 · 다음 스프린트 안내

```
다음 스프린트 시작:
/kangnam-dev:sprint-planning <project> <next-version>
```

## NEVER 규칙

1. NEVER: progress.md가 evergreen 아닌데 review를 evergreen으로 만들지 마라 (스크립트가 자동으로 draft로 시작).
2. NEVER: 4L 카테고리 임의 변형하지 마라 — `~/wiki/Concepts/4L-Retrospective.md` SSOT.
3. NEVER: Action Items가 비어있는 review.md commit하지 마라.
4. NEVER: Rule 업데이트를 사용자 승인 없이 자동 적용하지 마라.

## ALWAYS 규칙

1. ALWAYS: 스크립트로 스캐폴드 → retrospective 스킬로 본문 작성 순서.
2. ALWAYS: planning.md + progress.md를 컨텍스트로 retrospective에 전달.
3. ALWAYS: review.md를 `Projects/<project>/Sprints/<version>/review.md`에 저장.
4. ALWAYS: Action Items 섹션 + Rule 업데이트 후보 제시로 마무리.
