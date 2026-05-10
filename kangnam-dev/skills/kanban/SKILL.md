---
name: kanban
description: "Personal kanban board management in ~/wiki/Kanban/ — create cards, move between columns (Backlog/InProgress/Done/Blocked), update metadata, view the board. Use this skill whenever the user mentions kanban, 칸반, board, 보드, asks about current work in progress, says things like '백로그에 추가', 'Done으로 옮겨', '진행 중으로', '블록됐어', '지금 뭐 하고 있지', '보드 보여줘', or types /kanban. All mutations go through Python scripts to prevent file-level mistakes; never mv or edit card files directly."
---

# Kanban

Personal kanban board for tracking work across projects in `~/wiki/Kanban/`.

The board is a directory of markdown cards organized into column folders. A single user manages the board across Mac/Ubuntu/Windows via `ai-config-sync`, so all mutations go through Python scripts that handle frontmatter, IDs, and the auto-generated index file consistently. Never mutate card files directly.

## Board layout

```
~/wiki/Kanban/
├── Backlog/      # not started
├── InProgress/   # actively working
├── Done/         # completed
├── Blocked/      # waiting on something
├── Archive/      # soft-deleted
├── BOARD.md      # auto-generated index (read this for board state)
└── .schema.json  # frontmatter schema (validation)
```

A card is one markdown file. The folder it sits in IS its status — moving folders = changing status. Filename is a slug (`fix-sync-bug.md`); the stable ID lives in frontmatter (`id: 260429-1503`).

## Card format

```yaml
---
id: 260429-1503                            # auto: YYMMDD-HHMM
created: 2026-04-29T15:03:42+09:00         # auto: ISO timestamp
title: 동기화 mtime 비교 버그 수정          # required
project: ai-config-sync                    # required (auto-inferred from cwd)
priority: med                              # optional: high | med | low
tags: [bug, sync]                          # optional
due: 2026-05-15                            # optional
type: task                                 # optional: task | epic (default task)
epic: 260415-1020                          # optional: parent epic id
blocked_by: 260420-0901                    # auto when moved to Blocked
completed_at: 2026-05-01T10:23:00+09:00    # auto when moved to Done
---

## 배경
...

## 할 일
- [ ] ...

## 메모
...
```

Body content is free markdown — edit it directly with the Edit tool when the user wants to add notes, checklists, or context. Frontmatter changes go through scripts.

## How to use this skill

When the user invokes kanban-related intent, identify the operation and call the matching script. Scripts live in `scripts/` next to this file (resolve via `${SKILL_DIR}/scripts/<name>.py`).

After any mutation, the script auto-regenerates `BOARD.md`. To show the board state, read `~/wiki/Kanban/BOARD.md` — it's the single source of truth for "what's the current state."

### First-time setup

If `~/wiki/Kanban/` doesn't exist yet, run `kanban-init.py` to create the directory structure, schema, and an empty BOARD.md. Other scripts will refuse to run until init is done.

### Operations

| Intent | Script | Example |
|---|---|---|
| Create card | `kanban-new.py` | `uv run ${SKILL_DIR}/scripts/kanban-new.py "동기화 버그 수정" --type task --priority high --tags bug,sync` |
| View board | (read `BOARD.md`) | If stale, run `kanban-board.py` first to regenerate |
| Move card | `kanban-move.py` | `uv run ${SKILL_DIR}/scripts/kanban-move.py 260429-1503 inprogress` |
| Change metadata | `kanban-set.py` | `uv run ${SKILL_DIR}/scripts/kanban-set.py 260429-1503 --priority high --due 2026-05-15` |
| Delete card | `kanban-rm.py` | `uv run ${SKILL_DIR}/scripts/kanban-rm.py 260429-1503` (moves to Archive; `--hard` for real delete) |
| Validate | `kanban-validate.py` | Used by sync hook; reports schema violations |
| Rename project | `kanban-rename-project.py` | `uv run ${SKILL_DIR}/scripts/kanban-rename-project.py old-name new-name` |
| Regenerate board | `kanban-board.py` | Manual rebuild of BOARD.md |

Card identifiers accept either the ID (`260429-1503`) or the slug (`fix-sync-bug`). The scripts resolve either form; prefer the ID when there's any ambiguity.

### Project inference

When creating a card without `--project`, the script infers from:
1. cwd's git remote URL (last path segment)
2. cwd's folder name
3. If neither yields a usable name, the script errors and asks for `--project`.

The user can always override with `--project <name>`.

### Task/epic classification

The LLM using this skill decides whether a new backlog item is a `task` or an `epic` before calling `kanban-new.py`. The script is deterministic and only records the decision; it does not infer meaning from keywords.

- Concrete, checkable work becomes `--type task`.
- Broad or ambiguous ideas become `--type epic` and get the `needs-breakdown` tag automatically.
- Use `kanban-set.py <id> --type task|epic` to correct the classification later.
- Use `--note` to pass the user's raw thought/context; the LLM uses title + note to decide type, and the script writes the note into the card body.
- If confidence is low and the user is just capturing a thought, prefer `epic` over task. It is safer to break down later than to smuggle vague work into a sprint.

Examples:

```bash
uv run ${SKILL_DIR}/scripts/kanban-new.py "로그인 실패 메시지 수정" --type task

uv run ${SKILL_DIR}/scripts/kanban-new.py "결제 구조 개선" --type epic --note "언젠가 전체 결제 흐름을 정리하고 싶음"
```

During sprint planning, epic cards are not implemented directly. They are split into smaller Core Gates with `card: new` and `source_epic: <epic id>`.

## Communication style

Keep responses short. After a mutation, report just what changed in one line:
- "추가됨: [260429-1503] 동기화 버그 수정 → Backlog (ai-config-sync)"
- "이동: 260429-1503 → InProgress"
- "완료: 260429-1503 → Done (2026-05-01)"

For board views, show the BOARD.md content as-is — don't re-summarize it. The format is already optimized for at-a-glance reading.

## Boundaries

**Do not:**
- Move card files with `mv`, `cp`, or Write tool — always use `kanban-move.py`. Folder = status, and the script keeps frontmatter (`completed_at`, `blocked_by`) in sync with the move.
- Edit `BOARD.md` directly — it's regenerated and your edits will be lost. Run `kanban-board.py` to refresh.
- Generate IDs manually — the script handles `YYMMDD-HHMM` format and uniqueness.
- Touch frontmatter `id` or `created` — these are immutable after creation.

**Do (free to use Edit tool):**
- Edit card body content (notes, checklists, context sections below frontmatter).
- Read individual card files to answer "what's in this card."

## Retrospective integration

The `retrospective` skill reads `Done/` cards (frontmatter + body) plus `git log` to build 4L analysis. No special fields are needed — kanban tracks work, retro analyzes it. If the user wants reflection notes on a card, encourage them to write a free `## 회고` section in the body; retro will pick it up naturally.
