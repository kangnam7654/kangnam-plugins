#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Move a card to a different column. Updates frontmatter accordingly."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _kanban import (
    ID_PATTERN,
    KANBAN_ROOT,
    ensure_initialized,
    fail,
    find_card,
    normalize_column,
    now_iso,
    regenerate_board,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Move a kanban card to a column.")
    p.add_argument("identifier", help="Card id (260429-1503) or slug")
    p.add_argument("column", help="Target column: backlog/inprogress/done/blocked")
    p.add_argument("--by", help="Blocker card id (only when target is Blocked)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ensure_initialized()

    card = find_card(args.identifier)
    target = normalize_column(args.column)
    if target == "Archive":
        fail("use kanban-rm.py to archive a card.")

    fm = dict(card.frontmatter)

    if target == "Done":
        fm["completed_at"] = now_iso()
        fm.pop("blocked_by", None)
    elif target == "Blocked":
        if args.by:
            if not ID_PATTERN.match(args.by):
                fail(f"--by must be a card id (YYMMDD-HHMM), got '{args.by}'")
            fm["blocked_by"] = args.by
        # If blocked without --by, leave any existing blocked_by intact.
    else:
        fm.pop("blocked_by", None)
        fm.pop("completed_at", None)

    new_path = KANBAN_ROOT / target / card.path.name
    if new_path.exists() and new_path != card.path:
        fail(f"target file already exists: {new_path}")

    # Write to new location with updated frontmatter, then remove old.
    from _kanban import write_card

    write_card(new_path, fm, card.body)
    if new_path != card.path:
        card.path.unlink()

    regenerate_board()
    print(f"moved: {fm['id']} {card.column} -> {target}")
    if target == "Done":
        print(f"  completed_at: {fm['completed_at']}")
    if target == "Blocked" and "blocked_by" in fm:
        print(f"  blocked_by: {fm['blocked_by']}")


if __name__ == "__main__":
    main()
