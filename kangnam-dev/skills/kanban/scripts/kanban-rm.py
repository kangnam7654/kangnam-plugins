#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Archive a card (default) or hard-delete it."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _kanban import (
    KANBAN_ROOT,
    ensure_initialized,
    fail,
    find_card,
    regenerate_board,
    write_card,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Remove a kanban card.")
    p.add_argument("identifier", help="Card id or slug")
    p.add_argument(
        "--hard",
        action="store_true",
        help="Permanently delete (default: move to Archive/)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ensure_initialized()

    card = find_card(args.identifier)

    if args.hard:
        card.path.unlink()
        regenerate_board()
        print(f"deleted: {card.id} ({card.path.name})")
        return

    target = KANBAN_ROOT / "Archive" / card.path.name
    if target.exists():
        fail(f"file already exists in Archive: {target}")
    write_card(target, card.frontmatter, card.body)
    card.path.unlink()
    regenerate_board()
    print(f"archived: {card.id} {card.column} -> Archive")


if __name__ == "__main__":
    main()
