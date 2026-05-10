#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Scaffold a sprint's review.md and prepare retrospective context.

Usage:
  sprint-review.py <project> <version> [--force]

What it does (safe / structured parts):
- Validates sprint kanban cards are all Done
- Reads planning.md + done card metadata to derive period/gates
- Creates review.md skeleton with frontmatter + period + gate summary
- Prints retrospective context bundle for AI to fill in 4L sections

It does NOT:
- Generate 4L retrospective content (AI calls retrospective skill after)
- Push (NEVER)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _sprint import (  # type: ignore
    FrontmatterError,
    confirm_overwrite,
    extract_core_gates,
    git_add,
    normalize_version,
    parse_frontmatter,
    project_dir,
    sprint_dir,
    today,
    write_with_frontmatter,
)
from _agent_kanban import project_working_dir, sprint_cards as load_sprint_cards  # type: ignore


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scaffold sprint review.md.")
    p.add_argument("project")
    p.add_argument("version")
    p.add_argument("--force", action="store_true", help="Overwrite existing review.md")
    p.add_argument(
        "--allow-open-cards",
        action="store_true",
        help="Allow scaffolding review.md even if sprint kanban cards are not all Done",
    )
    p.add_argument("--working-dir", help="Code/project directory whose .kanban board should be used. Default: ~/projects/<project>")
    return p.parse_args()


def sprint_cards(project: str, version: str, working_dir: Path) -> tuple[list[dict], list[dict]]:
    """Return (open_cards, done_cards) for non-epic project+sprint cards."""
    open_cards: list[dict] = []
    done_cards: list[dict] = []
    for card in load_sprint_cards(project, version, working_dir, include_done=True):
        if card.get("kind") == "epic":
            continue
        normalized = {
            "id": card.get("id"),
            "title": card.get("title"),
            "gate": card.get("gate") or "",
            "column": card.get("column") or card.get("status"),
            "path": card.get("path"),
            "completedAt": card.get("completedAt"),
            "updatedAt": card.get("updatedAt"),
        }
        if card.get("status") == "done":
            done_cards.append(normalized)
        else:
            open_cards.append(normalized)

    return open_cards, done_cards


REVIEW_TEMPLATE = """\
# Sprint Retro: {project} — {version} {summary_placeholder}

_{period}_

## 스프린트 개요

- 게이트별 결과: **채워주세요** (planning.md의 Core Gates와 Done 카드의 테스트/활동 로그 참고)
- commit 흐름: **채워주세요**
- 의도와 다르게 흘러간 것: **채워주세요**

## 게이트 정의 학습

> 다음 스프린트의 planning을 더 정확하게 만들기 위한 메타 회고. 이번 게이트 *정의 자체*를 돌아본다 (실행이 아니라).

- **3-튜플 정의 적정성**: happy/isolation_failure/expected_reaction이 실제 운영에서 정확히 들어맞았나? 빠진 케이스 / 너무 넓었던 시나리오 / 어긋난 반응이 있었나? — **채워주세요**
- **게이트 사이즈**: 각 게이트가 선언한 페이스 안에 들어갔나? (standard 기준 1~3일) 너무 컸던 / 너무 작아 합쳤어야 할 게이트? — **채워주세요**
- **도메인 분배**: `domain:` 라벨이 실제 작업과 일치했는가? 다음에 분리/통합할 게이트? (예: backend라 했는데 frontend 작업이 절반) — **채워주세요**
- **자동화 적정성**: `검증:` 명령이 정상 작동했나? `manual`로 둔 시나리오 중 자동화 가능했던 것? 명령은 박혔지만 실제로는 깨졌던 것? — **채워주세요**

## Liked (좋았던 것)

- **AI/사용자가 4L 기법으로 채움**

## Learned (배운 것)

- **AI/사용자가 4L 기법으로 채움**

## Lacked (부족했던 것)

- **AI/사용자가 4L 기법으로 채움**

## Longed For (다음에 원하는 것)

- **AI/사용자가 4L 기법으로 채움**

## Action Items

- [ ] **다음 스프린트로 carry-over할 항목**
- [ ] **Rule 업데이트 후보**

---

_4L 기준 정의: [[../../../../Concepts/4L-Retrospective]]_
"""


def main() -> None:
    args = parse_args()
    project_dir(args.project)
    version = normalize_version(args.project, args.version)
    working_dir = project_working_dir(args.project, args.working_dir)
    sd = sprint_dir(args.project, version)
    planning_path = sd / "planning.md"
    review_path = sd / "review.md"

    if not planning_path.is_file():
        print(f"error: planning.md missing: {planning_path}", file=sys.stderr)
        sys.exit(2)

    gates = extract_core_gates(planning_path)
    open_cards, done_cards = sprint_cards(args.project, version, working_dir)
    if gates and not open_cards and not done_cards and not args.allow_open_cards:
        print(
            f"error: no kanban cards found for {args.project} {version}.\n"
            f"Run sprint-planning card publication or pass --allow-open-cards "
            f"to write a draft review.md for a legacy sprint.",
            file=sys.stderr,
        )
        sys.exit(2)
    if open_cards and not args.allow_open_cards:
        print(
            f"error: sprint has {len(open_cards)} kanban card(s) not in Done.\n"
            f"Finish or explicitly carry over cards before review, or pass "
            f"--allow-open-cards to write a draft review.md.",
            file=sys.stderr,
        )
        for card in open_cards[:10]:
            gate = f" gate={card['gate']}" if card["gate"] else ""
            print(
                f"  - [{card['id']}] {card['title']} ({card['column']}{gate})",
                file=sys.stderr,
            )
        if len(open_cards) > 10:
            print(f"  ... and {len(open_cards) - 10} more", file=sys.stderr)
        sys.exit(2)

    confirm_overwrite(review_path, force=args.force)

    try:
        planning_fm, _ = parse_frontmatter(planning_path)
    except FrontmatterError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    period_start = planning_fm.get("created", "?")
    done_dates = [
        str(card.get("completedAt") or card.get("updatedAt") or "")
        for card in done_cards
        if card.get("completedAt") or card.get("updatedAt")
    ]
    period_end = max(done_dates) if done_dates else today()
    period = f"{period_start} ~ {period_end}"

    review_status = "draft" if open_cards else "growing"

    fm = {
        "created": today(),
        "updated": today(),
        "type": "sprint-retro",
        "status": review_status,
        "project": args.project,
        "sprint": f"{version} — <한 줄 요약>",
        "period": period,
    }
    body = REVIEW_TEMPLATE.format(
        project=args.project,
        version=version,
        summary_placeholder="<한 줄 요약>",
        period=period,
    )
    write_with_frontmatter(review_path, fm, body)
    git_add(review_path)

    print(f"\n✓ scaffolded: {review_path}")
    print(f"  status: {review_status}")
    print(f"  period: {period}")
    print(f"  Kanban: {working_dir}/.kanban/kanban-data.json")
    print(f"  gates from planning.md: {len(gates)}")
    print(f"  done cards: {len(done_cards)}")
    print()
    print("다음 단계 — retrospective 스킬을 호출하여 본문 작성:")
    print()
    print("  아래 컨텍스트를 retrospective 스킬에 전달하세요.")
    print("  retrospective가 본문을 채우고 critic PASS 후 status를 evergreen으로 바꿉니다.")
    print()
    print(f"    mode: sprint")
    print(f"    project: {args.project}")
    print(f"    sprint: {version}")
    print(f"    period_start: {period_start}")
    print(f"    period_end: {period_end}")
    print(f"    output_path: {review_path}")
    print(f"    context_files:")
    print(f"      - {planning_path}")
    if done_cards:
        print(f"    done_cards:")
        for card in done_cards:
            gate = f" gate={card['gate']}" if card["gate"] else ""
            print(f"      - [{card['id']}] {card['title']} ({card['path']}{gate})")


if __name__ == "__main__":
    main()
