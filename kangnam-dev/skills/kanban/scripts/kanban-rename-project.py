#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Bulk-rename frontmatter `project:` field across all cards."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _kanban import (
    ALL_FOLDERS,
    ensure_initialized,
    iter_cards,
    regenerate_board,
    write_card,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Rename project across all kanban cards.")
    p.add_argument("old", help="Old project name")
    p.add_argument("new", help="New project name")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ensure_initialized()

    changed = 0
    for card in iter_cards(ALL_FOLDERS):
        if card.frontmatter.get("project") != args.old:
            continue
        if args.dry_run:
            print(f"would rename: {card.path}")
        else:
            fm = dict(card.frontmatter)
            fm["project"] = args.new
            write_card(card.path, fm, card.body)
        changed += 1

    if not args.dry_run and changed:
        regenerate_board()

    label = "would rename" if args.dry_run else "renamed"
    print(f"{label}: {changed} cards ({args.old} -> {args.new})")


if __name__ == "__main__":
    main()
