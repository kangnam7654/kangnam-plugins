#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Update card metadata fields (priority/due/tags/epic/title/type)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _kanban import (
    ID_PATTERN,
    ensure_initialized,
    fail,
    find_card,
    parse_tags,
    regenerate_board,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Update card metadata.")
    p.add_argument("identifier", help="Card id or slug")
    p.add_argument("--title", help="New title")
    p.add_argument("--priority", choices=["high", "med", "low", "none"])
    p.add_argument("--due", help="Due date (YYYY-MM-DD), or 'none' to clear")
    p.add_argument("--tags", help="Comma-separated tags, or 'none' to clear")
    p.add_argument("--epic", help="Parent epic id, or 'none' to clear")
    p.add_argument("--type", choices=["task", "epic", "none"], help="Card type, or 'none' to clear")
    p.add_argument("--project", help="Change project name (this card only)")
    p.add_argument("--sprint", help="Sprint/version, or 'none' to clear")
    p.add_argument("--gate", help="Readiness gate (e.g., G1), or 'none' to clear")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ensure_initialized()

    card = find_card(args.identifier)
    fm = dict(card.frontmatter)
    changed: list[str] = []

    if args.title:
        fm["title"] = args.title
        changed.append("title")
    if args.priority:
        if args.priority == "none":
            fm.pop("priority", None)
        else:
            fm["priority"] = args.priority
        changed.append("priority")
    if args.due:
        if args.due == "none":
            fm.pop("due", None)
        else:
            fm["due"] = args.due
        changed.append("due")
    if args.tags is not None:
        if args.tags == "none":
            fm.pop("tags", None)
        else:
            fm["tags"] = parse_tags(args.tags)
        changed.append("tags")
    if args.epic:
        if args.epic == "none":
            fm.pop("epic", None)
        else:
            if not ID_PATTERN.match(args.epic):
                fail(f"--epic must be a card id (YYMMDD-HHMM), got '{args.epic}'")
            fm["epic"] = args.epic
        changed.append("epic")
    if args.type:
        if args.type == "none" or args.type == "task":
            fm.pop("type", None)
        else:
            fm["type"] = args.type
        changed.append("type")
    if args.project:
        fm["project"] = args.project
        changed.append("project")
    if args.sprint:
        if args.sprint == "none":
            fm.pop("sprint", None)
        else:
            fm["sprint"] = args.sprint
        changed.append("sprint")
    if args.gate:
        if args.gate == "none":
            fm.pop("gate", None)
        else:
            import re as _re
            if not _re.match(r"^G\d+$", args.gate):
                fail(f"--gate must be like 'G1', 'G2', got '{args.gate}'")
            fm["gate"] = args.gate
        changed.append("gate")

    if not changed:
        fail("nothing to update. Pass at least one of --title/--priority/--due/--tags/--epic/--type/--project/--sprint/--gate")

    from _kanban import write_card

    write_card(card.path, fm, card.body)
    regenerate_board()
    print(f"updated {fm['id']}: {', '.join(changed)}")


if __name__ == "__main__":
    main()
