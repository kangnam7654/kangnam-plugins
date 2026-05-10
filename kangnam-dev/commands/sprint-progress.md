---
description: "스프린트 진행 상황 추적. progress.md 스캐폴드 + 게이트 상태 + Kanban 정합성 + --freeze 동결."
argument-hint: "<project> <version> [--freeze]"
disable-model-invocation: true
---

Raw slash-command arguments:
`$ARGUMENTS`

# sprint-progress

`<plugin-root>`는 이 plugin의 `kangnam-dev/` 디렉토리다. 체크아웃에서 실행하면 `/Users/kangnam/projects/kangnam-plugins/kangnam-dev`, 설치본에서 실행하면 설치된 plugin의 `kangnam-dev` 루트로 해석한다.

진행 중인 스프린트의 게이트 체크리스트(progress.md)를 관리. **Python 스크립트가 구조/검증을 처리**하고, AI/사용자는 게이트 검증 결과를 채워넣는다.

## 절차

### Step 1 · 스크립트 실행

```bash
uv run <plugin-root>/scripts/sprint/sprint-progress.py $ARGUMENTS
```

세 가지 모드로 동작:

**A. progress.md 없을 때 → 스캐폴드**
- planning.md의 Core Gates를 추출해서 체크리스트 자동 생성
- 각 게이트에 `[ ]` happy / isolation_failure / expected_reaction 3-튜플 자리 마련

**B. progress.md 있을 때 (--freeze 없음) → 진행 보고**
- 게이트 ✅/총개 출력
- Kanban 카드 (sprint=<version>) InProgress/Backlog/Done 분포
- 다음 행동 제안 (모두 ✅이면 동결 가능 안내)

**C. `--freeze` 플래그 → 동결**
- 모든 게이트 ✅ 검증
- 플레이스홀더(`<검증 메모, 날짜>`)가 남은 [x] 거부
- `status: growing` → `evergreen`
- 제목 `(DRAFT)` → `(CLOSED)`
- `--force`로 검증 우회 가능 (권장 안 함)

### Step 2 · 게이트 검증 메모 채우기 (AI/사용자)

스크립트가 만든 progress.md에서 각 게이트 검증 진행 시 아래를 갱신:

- 체크박스: `- [ ]` → `- [x]`
- 메모: `<검증 메모, 날짜>` → 실제 검증 내용 + 날짜 + commit hash
- 검증 로그 표에 행 추가 (append-only — 기존 행 절대 수정 안 함)

예시:
```markdown
- [x] **happy** — POST /api/todos 정상 응답, status 200, body 검증. _2026-05-08 commit `abc1234`_
```

### Step 3 · Kanban 정합성 (스크립트가 자동 검증)

`sprint-progress.py`의 report 모드는 이제 게이트-카드 정합성을 자동으로 검사하고 경고를 출력한다. 두 가지 mismatch:

1. **게이트 ✅인데 카드는 Done 아님** — 검증 끝났지만 보드 안 옮김
2. **카드 Done인데 게이트는 [ ]** — 보드 옮겼지만 검증 메모 누락

매칭 키: `progress.md`의 `### G<N>` 헤딩 ↔ 카드 frontmatter의 `gate: G<N>` 필드. (sprint-planning이 `sprint-publish-cards.py`로 발행한 카드는 `gate` 필드를 자동으로 가짐.)

자동 이동은 **하지 않는다** — 검증 메모는 사람이 직접 채워야 하므로. 스크립트는 경고와 명령어 힌트만 제공:

```bash
uv run <plugin-root>/skills/kanban/scripts/kanban-move.py <id> done
```

사용자가 결정 후 직접 실행.

### Step 4 · 커밋

```bash
git -C ~/wiki commit -m "sprint(<project>): <version> progress update"
```

`--freeze` 시:
```bash
git -C ~/wiki commit -m "sprint(<project>): <version> readiness frozen"
```

## NEVER 규칙

1. NEVER: 게이트 체크박스를 검증 메모/날짜 없이 [x] 표기하지 마라.
2. NEVER: 검증 로그 표의 기존 행을 수정하지 마라 (append-only).
3. NEVER: 스크립트가 거부한 동결을 `--force`로 우회할 때 사용자 확인 없이 진행하지 마라.
4. NEVER: `git push` 자동 실행하지 마라.

## ALWAYS 규칙

1. ALWAYS: 스크립트를 먼저 호출 (직접 progress.md 만들거나 동결하지 마라).
2. ALWAYS: 게이트는 3-튜플로 추적.
3. ALWAYS: Kanban 보드와 게이트 상태 정합성 확인.
4. ALWAYS: deferred 항목은 progress.md Out-of-scope 섹션과 `deferred.md` 양쪽에 기록.
