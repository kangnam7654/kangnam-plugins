#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Publish kanban cards for a freshly planned sprint.

Idempotent: re-running on a sprint that already has cards skips creation but
still syncs carry-over labels.

What it does:
1. Reads planning.md to extract one-line summary + Core Gate headings.
2. Creates an epic card for the sprint (if not already present).
3. Creates one task card per Core Gate, linked to the epic, frontmatter
   carries `gate: G<N>` so sprint-progress can match cards to gates.
4. Updates the previous sprint's incomplete cards (Backlog/InProgress/Blocked)
   to point to the new sprint.

Skip flags:
- --no-epic         : skip creating the epic card
- --no-gate-cards   : skip creating gate-level cards
- --no-carryover    : skip carry-over sprint-label sync
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _sprint import (  # type: ignore
    WIKI_ROOT,
    FrontmatterError,
    extract_core_gates,
    normalize_version,
    parse_frontmatter,
    previous_sprint,
    project_dir,
    sprint_dir,
)

KANBAN_NEW = Path.home() / ".claude/skills/kanban/scripts/kanban-new.py"
KANBAN_SET = Path.home() / ".claude/skills/kanban/scripts/kanban-set.py"
KANBAN_ROOT = WIKI_ROOT / "Kanban"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Publish epic + gate cards for a sprint, sync carry-over labels.",
    )
    p.add_argument("project")
    p.add_argument("version")
    p.add_argument("--no-epic", action="store_true")
    p.add_argument("--no-gate-cards", action="store_true")
    p.add_argument("--no-carryover", action="store_true")
    return p.parse_args()


GATE_HEADING_RE = re.compile(
    r"^###\s+(?P<id>G\d+)[.\s\-]+(?P<name>.+?)\s*$",
    re.MULTILINE,
)


def parse_gates_with_names(planning_path: Path) -> list[tuple[str, str]]:
    """Return [(G1, '게이트 이름'), ...] from planning.md Core Gates section."""
    text = planning_path.read_text(encoding="utf-8")
    m = re.search(r"^## Core Gates\s*\n(.*?)(?=\n## |\Z)", text, re.S | re.M)
    if not m:
        return []
    section = m.group(1)
    out = []
    for hit in GATE_HEADING_RE.finditer(section):
        gid = hit.group("id")
        name = hit.group("name").strip().rstrip(".")
        # ignore the template placeholder
        if name.startswith("<") or "채워주세요" in name:
            continue
        out.append((gid, name))
    return out


def extract_one_line_summary(planning_path: Path) -> str:
    text = planning_path.read_text(encoding="utf-8")
    m = re.search(r"^## 한 줄 요약\s*\n+(.*?)(?=\n## |\Z)", text, re.S | re.M)
    if not m:
        return ""
    body = m.group(1).strip().splitlines()[0].strip()
    if body.startswith("<") or "채워주세요" in body:
        return ""
    return body


def find_existing_card(project: str, sprint: str, *, gate: str | None = None,
                       card_type: str | None = None) -> str | None:
    """Return card id if a card with matching project+sprint(+gate or type) exists."""
    for col in ("Backlog", "InProgress", "Blocked", "Done"):
        col_dir = KANBAN_ROOT / col
        if not col_dir.is_dir():
            continue
        for card in col_dir.glob("*.md"):
            try:
                fm, _ = parse_frontmatter(card, required=False)
            except FrontmatterError:
                continue
            if fm.get("project") != project:
                continue
            if fm.get("sprint") != sprint:
                continue
            if gate is not None and fm.get("gate") != gate:
                continue
            if card_type == "epic" and fm.get("type") != "epic":
                continue
            if card_type == "task" and fm.get("type") == "epic":
                continue
            return fm.get("id")
    return None


def run_kanban_new(*args: str) -> str:
    """Run kanban-new.py and return the new card's id from stdout."""
    result = subprocess.run(
        ["uv", "run", str(KANBAN_NEW), *args],
        capture_output=True, text=True, check=True,
    )
    m = re.search(r"^added: \[([\w\d-]+)\]", result.stdout, re.M)
    if not m:
        raise RuntimeError(f"could not parse card id from kanban-new output:\n{result.stdout}")
    return m.group(1)


def run_kanban_set(card_id: str, *args: str) -> None:
    subprocess.run(
        ["uv", "run", str(KANBAN_SET), card_id, *args],
        check=True,
    )


def sync_carryover(project: str, prev_sprint: str, new_sprint: str) -> list[str]:
    """Update sprint label of prev_sprint's incomplete cards to new_sprint.
    Returns list of card ids that were updated."""
    updated = []
    for col in ("Backlog", "InProgress", "Blocked"):
        col_dir = KANBAN_ROOT / col
        if not col_dir.is_dir():
            continue
        for card in col_dir.glob("*.md"):
            try:
                fm, _ = parse_frontmatter(card, required=False)
            except FrontmatterError:
                continue
            if fm.get("project") != project:
                continue
            if fm.get("sprint") != prev_sprint:
                continue
            cid = fm.get("id")
            if not cid:
                continue
            run_kanban_set(cid, "--sprint", new_sprint)
            updated.append(cid)
    return updated


def main() -> None:
    args = parse_args()
    project_dir(args.project)
    version = normalize_version(args.project, args.version)
    sd = sprint_dir(args.project, version)
    planning_path = sd / "planning.md"
    if not planning_path.is_file():
        print(f"error: planning.md missing: {planning_path}", file=sys.stderr)
        sys.exit(2)

    summary = extract_one_line_summary(planning_path)
    gates = parse_gates_with_names(planning_path)

    print(f"\n=== {args.project} {version} 카드 발행 ===")
    print(f"  한 줄 요약: {summary or '(비어있음)'}")
    print(f"  게이트: {len(gates)}개")
    print()

    # Step 1: Epic
    epic_id = None
    if not args.no_epic:
        epic_id = find_existing_card(args.project, version, card_type="epic")
        if epic_id:
            print(f"  ⤷ epic 이미 존재: [{epic_id}] (skip)")
        else:
            title = f"[{version}] {summary or '<요약 미기재>'}"
            epic_id = run_kanban_new(
                title,
                "--project", args.project,
                "--sprint", version,
                "--type", "epic",
                "--priority", "high",
            )
            print(f"  ✓ epic 발행: [{epic_id}]")

    # Step 2: Gate cards
    if not args.no_gate_cards:
        if not gates:
            print(f"  ⚠️ Core Gates에서 추출된 게이트 없음 — gate 카드 발행 skip")
        for gid, gname in gates:
            existing = find_existing_card(args.project, version, gate=gid)
            if existing:
                print(f"    ⤷ {gid} 카드 이미 존재: [{existing}] (skip)")
                continue
            title = f"[{version} {gid}] {gname}"
            new_args = [
                title,
                "--project", args.project,
                "--sprint", version,
                "--gate", gid,
                "--priority", "high",
            ]
            if epic_id:
                new_args.extend(["--epic", epic_id])
            cid = run_kanban_new(*new_args)
            print(f"    ✓ {gid} 발행: [{cid}] {gname}")

    # Step 3: Carry-over sync
    if not args.no_carryover:
        prev = previous_sprint(args.project, version)
        if prev:
            updated = sync_carryover(args.project, prev, version)
            if updated:
                print(f"\n  ✓ carry-over: {prev} → {version} 라벨 갱신 {len(updated)}장")
                for cid in updated:
                    print(f"      [{cid}]")
            else:
                print(f"\n  ⤷ carry-over: {prev}에 미완료 카드 없음")
        else:
            print(f"\n  ⤷ carry-over: 직전 스프린트 없음 (첫 스프린트)")


if __name__ == "__main__":
    main()
