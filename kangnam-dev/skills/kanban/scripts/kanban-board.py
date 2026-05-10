#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Regenerate ~/wiki/Kanban/BOARD.md from current card files."""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _kanban import (
    BOARD_PATH,
    COLUMNS,
    KANBAN_ROOT,
    Card,
    ensure_initialized,
    fail,
    iter_cards,
    now_iso,
    write_card,
)

PRIORITY_ORDER = {"high": 0, "med": 1, "low": 2}
DONE_LIMIT = 10


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Regenerate BOARD.md.")
    p.add_argument("--project", help="Filter by project")
    p.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip frontmatter self-heal pass (default: sync column ↔ frontmatter).",
    )
    return p.parse_args()


def sync_card_frontmatter(cards: list[Card]) -> int:
    """Self-heal pass: make frontmatter consistent with the card's actual column.

    Lets the user mv/cp cards between columns directly without breaking invariants.
    Returns the number of files rewritten.
    """
    fixed = 0
    for c in cards:
        fm = dict(c.frontmatter)
        changed = False
        if c.column == "Done":
            if "completed_at" not in fm:
                try:
                    mtime = dt.datetime.fromtimestamp(c.path.stat().st_mtime).astimezone()
                    fm["completed_at"] = mtime.isoformat(timespec="seconds")
                except OSError:
                    fm["completed_at"] = now_iso()
                changed = True
            if "blocked_by" in fm:
                fm.pop("blocked_by")
                changed = True
        elif c.column == "Blocked":
            if "completed_at" in fm:
                fm.pop("completed_at")
                changed = True
        else:  # Backlog, InProgress
            if "completed_at" in fm:
                fm.pop("completed_at")
                changed = True
            if "blocked_by" in fm:
                fm.pop("blocked_by")
                changed = True
        if changed:
            write_card(c.path, fm, c.body)
            rel = c.path.relative_to(KANBAN_ROOT)
            print(f"sync: {rel} ← column={c.column}")
            fixed += 1
    return fixed


def detect_duplicates(cards: list[Card]) -> list[str]:
    """Return error lines for any id that lives in multiple active columns."""
    by_id: dict[str, list[Card]] = {}
    for c in cards:
        by_id.setdefault(c.id, []).append(c)
    errors: list[str] = []
    for cid, group in by_id.items():
        if len(group) > 1:
            locs = ", ".join(f"{g.column}/{g.path.name}" for g in group)
            errors.append(f"duplicate id '{cid}' in: {locs}")
    return errors


def card_sort_key(c: Card) -> tuple:
    pr = PRIORITY_ORDER.get(c.frontmatter.get("priority", "med"), 1)
    due = c.frontmatter.get("due", "9999-99-99")
    return (pr, due, c.id)


def completion_sort_key(c: Card) -> str:
    """Done cards: sort by completed_at desc, fallback to mtime, then id."""
    ts = c.frontmatter.get("completed_at")
    if ts:
        return ts
    try:
        mtime = dt.datetime.fromtimestamp(c.path.stat().st_mtime)
        return mtime.isoformat()
    except OSError:
        return c.id


def fmt_card_line(c: Card) -> str:
    parts = [f"`[{c.id}]`", f"**{c.title}**", f"`{c.project}`"]
    if c.sprint:
        parts.append(f"📌 `{c.sprint}`")
    pri = c.frontmatter.get("priority")
    if pri:
        parts.append(pri)
    due = c.frontmatter.get("due")
    if due:
        parts.append(f"due {due}")
    blocked_by = c.frontmatter.get("blocked_by")
    if blocked_by:
        parts.append(f"⛔ blocked by `{blocked_by}`")
    tags = c.frontmatter.get("tags") or []
    if tags:
        parts.append("[" + ", ".join(tags) + "]")
    type_ = c.frontmatter.get("type")
    if type_ == "epic":
        parts.append("🪐 epic")
    epic = c.frontmatter.get("epic")
    if epic:
        parts.append(f"epic→`{epic}`")
    return "- " + " · ".join(parts)


def by_project_summary(cards_by_col: dict[str, list[Card]]) -> str:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {col: 0 for col in COLUMNS})
    sprint_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for col, cards in cards_by_col.items():
        if col == "Done":
            cards = cards[:DONE_LIMIT]
        for c in cards:
            counts[c.project][col] += 1
            sprint_label = c.sprint or "(no sprint)"
            sprint_counts[c.project][sprint_label] += 1

    if not counts:
        return ""
    lines = ["## By Project", ""]
    for project in sorted(counts):
        c = counts[project]
        total = sum(c.values())
        lines.append(
            f"### {project} ({total})"
        )
        lines.append(
            f"- Status: InProgress {c['InProgress']} · Backlog {c['Backlog']} · "
            f"Blocked {c['Blocked']} · Done(recent {DONE_LIMIT}) {c['Done']}"
        )
        sprints = sprint_counts[project]
        if sprints:
            sprint_str = " · ".join(
                f"`{s}` {n}" for s, n in sorted(sprints.items(), key=lambda x: x[0])
            )
            lines.append(f"- Sprints: {sprint_str}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    ensure_initialized()

    all_active = [c for c in iter_cards(COLUMNS)]

    dup_errors = detect_duplicates(all_active)
    if dup_errors:
        for e in dup_errors:
            print(f"FAIL {e}", file=sys.stderr)
        fail(
            "cross-column duplicates found. Resolve by moving the stale copy to "
            "Archive/ (or delete it) before regenerating BOARD."
        )

    if not args.no_sync:
        n = sync_card_frontmatter(all_active)
        if n:
            print(f"synced {n} card(s) to match column state")
            # Re-read cards so downstream sort sees fresh frontmatter.
            all_active = [c for c in iter_cards(COLUMNS)]

    cards_by_col: dict[str, list[Card]] = {col: [] for col in COLUMNS}
    for card in all_active:
        if args.project and card.project != args.project:
            continue
        cards_by_col[card.column].append(card)

    cards_by_col["Backlog"].sort(key=card_sort_key)
    cards_by_col["InProgress"].sort(key=card_sort_key)
    cards_by_col["Blocked"].sort(key=card_sort_key)
    cards_by_col["Done"].sort(key=completion_sort_key, reverse=True)

    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    parts: list[str] = ["# Kanban Board", ""]
    parts.append(f"> Auto-generated · last updated: {now}")
    parts.append("> Do not edit directly. Use kanban-* scripts to mutate.")
    if args.project:
        parts.append(f"> Filtered: project = {args.project}")
    parts.append("")

    section_titles = [
        ("InProgress", "In Progress"),
        ("Backlog", "Backlog"),
        ("Blocked", "Blocked"),
    ]
    for key, title in section_titles:
        cards = cards_by_col[key]
        parts.append(f"## {title} ({len(cards)})")
        parts.append("")
        if not cards:
            parts.append("_(empty)_")
        else:
            parts.extend(fmt_card_line(c) for c in cards)
        parts.append("")

    done = cards_by_col["Done"][:DONE_LIMIT]
    parts.append(f"## Done (recent {DONE_LIMIT})")
    parts.append("")
    if not done:
        parts.append("_(empty)_")
    else:
        for c in done:
            ts = c.frontmatter.get("completed_at", "?")
            parts.append(
                f"- `[{c.id}]` **{c.title}** · `{c.project}` · 완료 {ts[:10] if isinstance(ts, str) else '?'}"
            )
    parts.append("")

    summary = by_project_summary(cards_by_col)
    if summary:
        parts.append("---")
        parts.append("")
        parts.append(summary)

    BOARD_PATH.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    print(f"wrote: {BOARD_PATH}")


if __name__ == "__main__":
    main()
