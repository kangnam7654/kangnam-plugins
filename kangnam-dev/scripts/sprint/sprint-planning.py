#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Scaffold a new sprint's planning.md.

Usage:
  sprint-planning.py <project> <version> [<one-line-goal>] [--force]

What it does (safe / structured parts):
- Validates project folder exists
- Normalizes version per project convention (v-prefix or not)
- Refuses if planning.md already exists (unless --force)
- Creates Sprints/<version>/planning.md with frontmatter + carry-over from
  previous sprint's review.md
- Stages but does NOT commit (caller decides)
- Prints next-step instructions for filling in Core Gates

It does NOT:
- Generate Core Gate content (that's the AI's job after running this)
- Create Kanban cards (delegated to kanban-new.py — caller invokes)
- Push (NEVER)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _sprint import (  # type: ignore
    WIKI_ROOT,
    FrontmatterError,
    confirm_overwrite,
    extract_action_items,
    git_add,
    list_sprints,
    normalize_version,
    parse_frontmatter,
    previous_sprint,
    project_dir,
    sprint_dir,
    today,
    write_with_frontmatter,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Scaffold a new sprint planning.md.",
        epilog=(
            "Examples:\n"
            "  sprint-planning.py lunawave 0.0.8 'todo list 모바일 폼팩터'\n"
            "  sprint-planning.py dear-jeongbin v0.1.0 --scale micro\n"
            "\n"
            "Scale guides the critic's expectations (gate count, etc):\n"
            "  micro    — 1-2 게이트, 1-3일 분량\n"
            "  standard — 3-5 게이트, 1-2주 분량 (기본)\n"
            "  major    — 5+ 게이트, 2주+ 분량"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("project", help="Project folder name under ~/wiki/Projects/")
    p.add_argument("version", help="Sprint version (e.g., 0.0.6 or v0.1.0)")
    p.add_argument("goal", nargs="?", default="", help="One-line sprint goal")
    p.add_argument(
        "--scale", choices=("micro", "standard", "major"), default="standard",
        help="Sprint size class — drives critic's gate-count expectations (default: standard)",
    )
    p.add_argument("--force", action="store_true", help="Overwrite existing planning.md")
    p.add_argument(
        "--no-auto-archive",
        action="store_true",
        help="Accepted for slash-command orchestration; sprint-planning.py itself does not archive cards.",
    )
    p.add_argument(
        "--no-pull", action="store_true",
        help="Skip wiki pull (caller has already pulled)",
    )
    return p.parse_args()


KANBAN_COLUMNS = ("Backlog", "InProgress", "Blocked")


def build_sprint_intake(project: str, version: str, prev_sprint: str | None) -> str:
    """List open kanban cards that planning should explicitly adopt or defer."""
    kanban_root = WIKI_ROOT / "Kanban"
    if not kanban_root.is_dir():
        return "_(Kanban 보드 없음 — intake 카드 없음)_"

    rows: list[dict] = []
    for column in KANBAN_COLUMNS:
        col_dir = kanban_root / column
        if not col_dir.is_dir():
            continue
        for path in sorted(col_dir.glob("*.md")):
            try:
                fm, _ = parse_frontmatter(path, required=False)
            except FrontmatterError:
                continue
            if fm.get("project") != project:
                continue
            sprint = str(fm.get("sprint") or "")
            type_ = str(fm.get("type") or "task")
            if sprint == version:
                reason = "already-bound"
            elif not sprint:
                reason = "needs-breakdown-epic" if type_ == "epic" else "unassigned"
            elif prev_sprint and sprint == prev_sprint:
                reason = "carry-over-card"
            else:
                reason = f"old-or-other-sprint:{sprint}"

            rows.append({
                "id": fm.get("id") or path.stem,
                "title": fm.get("title") or path.stem,
                "column": column,
                "type": type_,
                "sprint": sprint or "(none)",
                "priority": fm.get("priority") or "none",
                "reason": reason,
            })

    if not rows:
        return "_(현재 프로젝트의 열린 Kanban intake 카드 없음)_"

    lines = [
        "> 아래 기존 Kanban 카드들은 이번 스프린트 범위 후보입니다. "
        "task 카드는 Core Gate의 `card` 필드에 카드 id를 쓰면 publish 단계가 sprint/gate/epic에 자동 연결합니다. "
        "epic 카드는 직접 구현하지 말고 `source_epic`으로 연결된 작은 `card: new` gate로 쪼갭니다. "
        "이번에 하지 않을 카드는 Out-of-scope에 이유를 적습니다.",
        "",
    ]
    for row in rows:
        lines.append(
            f"- [{row['id']}] {row['title']} — "
            f"type: {row['type']}, {row['column']}, sprint: {row['sprint']}, "
            f"priority: {row['priority']}, reason: {row['reason']}"
        )
    return "\n".join(lines)


PLANNING_TEMPLATE = """\
# {project} — {version} Planning

> {version} 스프린트 = {goal_or_placeholder}.

## ⏱️ 페이스

- 목표 기간: <N>일/주 — **채워주세요**
- 일 평균 작업: <시간> — **채워주세요**
- 끝나는 시점: <YYYY-MM-DD> — **채워주세요**

## 한 줄 요약

{goal_summary_placeholder}

## Sprint Intake Cards

{sprint_intake_block}

## 직전 스프린트 Carry-over

{carryover_block}

## Core Gates

> 각 게이트 = happy/isolation_failure/expected_reaction 3-튜플 + domain + 검증 명령.
> - **domain**: 어떤 도메인 에이전트가 구현할지 — `frontend` | `backend` | `mobile` | `data` | `devops` | `ai`
> - **card**: 기존 task 카드를 구현하면 카드 id(예: `260509-1420`), 새 카드가 필요하면 `new`
> - **source_epic**: 기존 epic에서 쪼개진 gate면 epic id, 아니면 `none`
> - **검증**: 실행 가능한 명령 (예: `pytest tests/test_g1_happy.py`) 또는 `manual` (사람이 검증)
> - 자세한 룰: [[../../../../Rules/SprintScope]]

### G1. <게이트 이름> — **채워주세요**
- **domain**: `<frontend|backend|mobile|data|devops|ai>`
- **card**: `<new|기존 카드 id>`
- **source_epic**: `<none|기존 epic id>`
- **happy** — <정상 케이스 검증>
  - 검증: `<실행 명령 또는 manual>`
- **isolation_failure** — <격리 실패 시>
  - 검증: `<실행 명령 또는 manual>`
- **expected_reaction** — <시스템이 자동으로 어떻게 반응해야 하는가>
  - 검증: `<실행 명령 또는 manual>`

### G2. ...

## Out-of-scope

<이번 스프린트에서 명시적으로 안 하는 것 — `deferred.md`로 이월 가능>
"""


def build_carryover(prev_review: Path | None) -> str:
    if prev_review is None or not prev_review.is_file():
        return "_(첫 스프린트 — carry-over 없음)_"
    items = extract_action_items(prev_review)
    if not items:
        return f"_(직전 [[../{prev_review.parent.name}/review|{prev_review.parent.name} review]]에 Action Items 없음)_"
    lines = [f"_직전 [[../{prev_review.parent.name}/review|{prev_review.parent.name} review]] Action Items:_"]
    lines.append("")
    lines.extend(items)
    return "\n".join(lines)


def main() -> None:
    args = parse_args()

    project_dir(args.project)  # validate
    version = normalize_version(args.project, args.version)
    if version != args.version:
        print(f"note: normalized version '{args.version}' → '{version}' to match project convention")

    sd = sprint_dir(args.project, version)
    planning_path = sd / "planning.md"
    confirm_overwrite(planning_path, force=args.force)

    prev = previous_sprint(args.project, version)
    prev_review = sprint_dir(args.project, prev) / "review.md" if prev else None
    sprint_intake = build_sprint_intake(args.project, version, prev)

    fm = {
        "created": today(),
        "updated": today(),
        "type": "project_spec",
        "status": "growing",
        "project": args.project,
        "sprint": version,
        "scale": args.scale,
    }
    body = PLANNING_TEMPLATE.format(
        project=args.project,
        version=version,
        goal_or_placeholder=args.goal or "<한 줄 목표 — 채워주세요>",
        goal_summary_placeholder=(
            args.goal if args.goal else "<왜 이 스프린트인가, 직전 스프린트 대비 무엇이 새로워지는가>"
        ),
        sprint_intake_block=sprint_intake,
        carryover_block=build_carryover(prev_review),
    )

    write_with_frontmatter(planning_path, fm, body)
    git_add(planning_path)

    existing = list_sprints(args.project)
    print()
    print(f"✓ 스프린트 시작: {args.project} {version}")
    print(f"  파일: {planning_path}")
    if prev:
        print(f"  직전 스프린트: {prev} (carry-over {len(extract_action_items(prev_review))}건)")
    else:
        print(f"  직전 스프린트: 없음 (첫 스프린트)")
    print(f"  현재 스프린트 목록: {', '.join(existing)}")
    print()
    print("다음 단계:")
    print(f"  1. {planning_path.name}의 Sprint Intake Cards를 보고 Core Gates에 card id 또는 new 매핑")
    print(f"  2. sprint-publish-cards.py가 기존 카드는 연결하고 new gate는 새 카드 발행")
    print(f"  3. git -C ~/wiki commit -m 'sprint({args.project}): {version} planning'")


if __name__ == "__main__":
    main()
