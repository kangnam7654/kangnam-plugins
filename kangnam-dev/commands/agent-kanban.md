---
description: "프로젝트 로컬 LLM 개발 칸반(agent-kanban) CLI/MCP/UI 사용. ~/wiki Kanban이 아니라 각 프로젝트의 .kanban 보드를 쓴다."
argument-hint: "[context|create|ui|mcp|help] [--cwd <project-dir>]"
---

Raw slash-command arguments:
`$ARGUMENTS`

# agent-kanban

이 명령은 프로젝트별 LLM 개발 칸반을 다룬다. 개인 `~/wiki/Kanban`이 아니라 현재 프로젝트의 `.kanban/kanban-data.json`이 원본이다.

`<plugin-root>`는 이 plugin의 `kangnam-dev/` 디렉터리다. 체크아웃에서 실행하면 `/Users/kangnam/projects/kangnam-plugins/kangnam-dev`, 설치본에서는 설치된 plugin 루트로 해석한다.

## 기본 사용

CLI를 우선 사용한다:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh context --cwd "$PWD"
```

새 작업을 시작해야 하면:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh create "큰 작업 묶음" --cwd "$PWD" --type epic --status ready --priority medium --next "작은 작업으로 쪼개기"
<plugin-root>/scripts/agent-kanban/agent-kanban.sh create "구체 작업 제목" --cwd "$PWD" --type task --epic KBN-1001 --status ready --priority medium --next "다음 행동"
<plugin-root>/scripts/agent-kanban/agent-kanban.sh claim KBN-1002 --cwd "$PWD" --session "<stable-session-id>"
```

진행 기록:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh progress KBN-1001 --cwd "$PWD" --msg "진행 내용" --files src/file.ts --test-command "npm test" --test-status passed --test-summary "관련 테스트 통과"
```

sprint/gate 메타데이터 연결:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh set KBN-1002 --cwd "$PWD" --project "<project>" --sprint "0.2.0" --gate "G1"
```

완료:

```bash
<plugin-root>/scripts/agent-kanban/agent-kanban.sh done KBN-1001 --cwd "$PWD" --summary "검증 후 완료"
```

## UI

사람이 볼 때:

```bash
cd <plugin-root>/mcp/agent-kanban
npm install
npm run dev
```

브라우저에서 `http://127.0.0.1:3001`을 연다.

UI 구조:

```txt
Epic
  Backlog | Ready | In Progress | Review | Blocked | Done
    Task cards
```

설명과 진행 기록은 Markdown으로 렌더링된다. 버튼은 `Claim`, `Move to Review`, `Mark blocked`, `Mark done`처럼 실제 동작이 드러나게 표시된다.

## MCP

MCP는 선택 사항이다. 직접 CLI 실행이 불가능한 클라이언트에서만 `.mcp.json`의 `agent-kanban` 서버를 사용한다.
