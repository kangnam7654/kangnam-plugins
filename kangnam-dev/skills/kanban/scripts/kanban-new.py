#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Create a new card in Backlog/."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _kanban import (
    KANBAN_ROOT,
    ensure_initialized,
    fail,
    infer_project,
    iter_cards,
    now_id,
    now_iso,
    parse_tags,
    regenerate_board,
    slugify,
    write_card,
)

BODY_TEMPLATE = """## 배경

(이 카드를 만든 이유와 컨텍스트)

## 할 일

- [ ]

## 메모

"""


def build_body(note: str) -> str:
    if not note.strip():
        return BODY_TEMPLATE
    return f"""## 배경

{note.strip()}

## 할 일

- [ ]

## 메모

"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create a kanban card in Backlog/.")
    p.add_argument("title", help="Card title")
    p.add_argument("--note", help="Initial context/body note for classification and card background")
    p.add_argument("--project", help="Project name (auto-inferred if omitted)")
    p.add_argument("--sprint", help="Sprint/version this card belongs to (e.g., 0.0.6, v0.1.0)")
    p.add_argument("--priority", choices=["high", "med", "low"])
    p.add_argument("--tags", help="Comma-separated tags")
    p.add_argument("--due", help="Due date (YYYY-MM-DD)")
    p.add_argument("--epic", help="Parent epic id (YYMMDD-HHMM)")
    p.add_argument("--gate", help="Sprint readiness gate this card maps to (e.g., G1, G2)")
    p.add_argument(
        "--type",
        choices=["task", "epic"],
        required=True,
        help="Card level. The LLM/skill decides this; the script only records it.",
    )
    p.add_argument("--slug", help="Custom slug (default: derived from title)")
    return p.parse_args()


def unique_slug(base: str) -> str:
    existing = {c.slug for c in iter_cards()}
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


def unique_id(existing: set[str]) -> str:
    base = now_id()
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


def main() -> None:
    args = parse_args()
    ensure_initialized()

    project = infer_project(args.project)
    existing_ids = {c.id for c in iter_cards()}
    slug = unique_slug(args.slug or slugify(args.title))
    card_id = unique_id(existing_ids)
    note = args.note or ""
    card_type = args.type

    fm: dict = {
        "id": card_id,
        "created": now_iso(),
        "title": args.title,
        "project": project,
    }
    if args.sprint:
        fm["sprint"] = args.sprint
    if card_type == "epic":
        fm["type"] = "epic"
    if args.priority:
        fm["priority"] = args.priority
    if args.tags:
        fm["tags"] = parse_tags(args.tags)
    if card_type == "epic":
        tags = list(fm.get("tags") or [])
        if "needs-breakdown" not in tags:
            tags.append("needs-breakdown")
        fm["tags"] = tags
    if args.due:
        fm["due"] = args.due
    if args.epic:
        fm["epic"] = args.epic
    if args.gate:
        import re as _re
        if not _re.match(r"^G\d+$", args.gate):
            fail(f"--gate must be like 'G1', 'G2', got '{args.gate}'")
        fm["gate"] = args.gate

    path = KANBAN_ROOT / "Backlog" / f"{slug}.md"
    if path.exists():
        fail(f"file already exists: {path}")
    write_card(path, fm, build_body(note))
    regenerate_board()
    print(f"added: [{card_id}] {args.title} -> Backlog ({project})")
    print(f"type: {card_type}")
    print(f"file:  {path}")


if __name__ == "__main__":
    main()
