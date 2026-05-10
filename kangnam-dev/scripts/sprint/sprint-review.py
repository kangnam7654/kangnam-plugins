#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Scaffold a sprint's review.md and prepare retrospective context.

Usage:
  sprint-review.py <project> <version> [--force]

What it does (safe / structured parts):
- Validates progress.md is frozen (status: evergreen) — warns if not
- Reads planning.md + progress.md to derive period/gates
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
    WIKI_ROOT,
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scaffold sprint review.md.")
    p.add_argument("project")
    p.add_argument("version")
    p.add_argument("--force", action="store_true", help="Overwrite existing review.md")
    p.add_argument(
        "--allow-unfrozen", action="store_true",
        help="Allow scaffolding review.md even if progress.md is not evergreen",
    )
    p.add_argument(
        "--allow-open-cards",
        action="store_true",
        help="Allow scaffolding review.md even if sprint kanban cards are not all Done",
    )
    return p.parse_args()


KANBAN_COLUMNS = ("Backlog", "InProgress", "Blocked", "Done")


def sprint_cards(project: str, version: str) -> tuple[list[dict], list[dict]]:
    """Return (open_cards, done_cards) for non-epic project+sprint cards."""
    open_cards: list[dict] = []
    done_cards: list[dict] = []
    root = WIKI_ROOT / "Kanban"
    if not root.is_dir():
        return open_cards, done_cards

    for column in KANBAN_COLUMNS:
        col_dir = root / column
        if not col_dir.is_dir():
            continue
        for path in sorted(col_dir.glob("*.md")):
            try:
                fm, _ = parse_frontmatter(path, required=False)
            except FrontmatterError:
                continue
            if fm.get("project") != project or fm.get("sprint") != version:
                continue
            if fm.get("type") == "epic":
                continue
            card = {
                "id": fm.get("id") or path.stem,
                "title": fm.get("title") or path.stem,
                "gate": fm.get("gate") or "",
                "column": column,
                "path": str(path),
            }
            if column == "Done":
                done_cards.append(card)
            else:
                open_cards.append(card)

    return open_cards, done_cards


REVIEW_TEMPLATE = """\
# Sprint Retro: {project} — {version} {summary_placeholder}

_{period}_

## 스프린트 개요

- 게이트별 결과: **채워주세요** (planning.md의 Core Gates와 progress.md의 검증 로그 참고)
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
    sd = sprint_dir(args.project, version)
    planning_path = sd / "planning.md"
    progress_path = sd / "progress.md"
    review_path = sd / "review.md"

    if not planning_path.is_file():
        print(f"error: planning.md missing: {planning_path}", file=sys.stderr)
        sys.exit(2)
    if not progress_path.is_file():
        print(f"error: progress.md missing: {progress_path}", file=sys.stderr)
        sys.exit(2)

    try:
        progress_fm, _ = parse_frontmatter(progress_path)
    except FrontmatterError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    if "status" not in progress_fm:
        print(
            f"error: progress.md frontmatter has no 'status' field. "
            f"Cannot determine if frozen. Fix the file before retry.",
            file=sys.stderr,
        )
        sys.exit(2)
    progress_status = progress_fm["status"]
    if progress_status != "evergreen" and not args.allow_unfrozen:
        print(
            f"error: progress.md is not frozen (status={progress_status}).\n"
            f"Run: sprint-progress.py {args.project} {version} --freeze\n"
            f"Or pass --allow-unfrozen to write a draft review.md.",
            file=sys.stderr,
        )
        sys.exit(2)

    gates = extract_core_gates(planning_path)
    open_cards, done_cards = sprint_cards(args.project, version)
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
    period_end = progress_fm.get("updated", today())
    period = f"{period_start} ~ {period_end}"

    review_status = "growing" if progress_status == "evergreen" else "draft"

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
    print(f"      - {progress_path}")
    if done_cards:
        print(f"    done_cards:")
        for card in done_cards:
            gate = f" gate={card['gate']}" if card["gate"] else ""
            print(f"      - [{card['id']}] {card['title']} ({card['path']}{gate})")


if __name__ == "__main__":
    main()
