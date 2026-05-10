#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Publish kanban cards for a freshly planned sprint.

Idempotent: re-running on a sprint that already has cards skips creation and
re-applies explicit existing-card mappings.

What it does:
1. Reads planning.md to extract one-line summary + Core Gate headings.
2. Creates an epic card for the sprint (if not already present).
3. Creates one task card per Core Gate, linked to the epic, frontmatter
   carries `gate: G<N>` so sprint-progress can match cards to gates.
4. Reports previous sprint's incomplete cards. Explicit `card: <id>` mappings
   are the supported way to adopt old/backlog cards into this sprint.

Skip flags:
- --no-epic         : skip creating the epic card
- --no-gate-cards   : skip creating gate-level cards
- --no-carryover    : skip carry-over report
- --legacy-carryover: blindly relabel previous sprint's open cards (legacy mode)
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

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
BUNDLED_KANBAN_SCRIPTS = PLUGIN_ROOT / "skills" / "kanban" / "scripts"


def bundled_kanban_script(name: str) -> Path:
    bundled = BUNDLED_KANBAN_SCRIPTS / name
    if bundled.is_file():
        return bundled
    raise FileNotFoundError(f"bundled kanban script missing: {bundled}")


KANBAN_NEW = bundled_kanban_script("kanban-new.py")
KANBAN_SET = bundled_kanban_script("kanban-set.py")
KANBAN_ROOT = WIKI_ROOT / "Kanban"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Publish epic + gate cards for a sprint, adopting existing card mappings.",
    )
    p.add_argument("project")
    p.add_argument("version")
    p.add_argument("--no-epic", action="store_true")
    p.add_argument("--no-gate-cards", action="store_true")
    p.add_argument("--no-carryover", action="store_true")
    p.add_argument(
        "--legacy-carryover",
        action="store_true",
        help="Also relabel all previous sprint open cards to this sprint. Prefer explicit gate card mappings.",
    )
    return p.parse_args()


GATE_HEADING_RE = re.compile(
    r"^###\s+(?P<id>G\d+)[.\s\-]+(?P<name>.+?)\s*$",
    re.MULTILINE,
)
CARD_ID_RE = re.compile(r"^\[?(\d{6}-\d{4}(?:-\d+)?)\]?$")


def strip_ticks(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`") and len(value) >= 2:
        return value[1:-1].strip()
    return value.strip()


def parse_gates_with_names(planning_path: Path) -> list[dict]:
    """Return gate metadata from planning.md Core Gates section."""
    text = planning_path.read_text(encoding="utf-8")
    m = re.search(r"^## Core Gates\s*\n(.*?)(?=\n## |\Z)", text, re.S | re.M)
    if not m:
        return []
    section = m.group(1)
    hits = list(GATE_HEADING_RE.finditer(section))
    out: list[dict] = []
    for i, hit in enumerate(hits):
        gid = hit.group("id")
        name = hit.group("name").strip().rstrip(".")
        # ignore the template placeholder
        if name.startswith("<") or "채워주세요" in name:
            continue
        start = hit.end()
        end = hits[i + 1].start() if i + 1 < len(hits) else len(section)
        block = section[start:end]
        card_ref = ""
        card_m = re.search(r"^-\s+\*\*card\*\*:\s*(.+?)\s*$", block, re.M)
        if card_m:
            card_ref = strip_ticks(card_m.group(1))
        source_epic = ""
        source_m = re.search(r"^-\s+\*\*source_epic\*\*:\s*(.+?)\s*$", block, re.M)
        if source_m:
            source_epic = strip_ticks(source_m.group(1))
        out.append({"id": gid, "name": name, "card": card_ref, "source_epic": source_epic})
    return out


def normalize_card_ref(value: str) -> str:
    value = strip_ticks(value)
    if not value or value.lower() in {"new", "none", "n/a", "na", "-"}:
        return ""
    m = CARD_ID_RE.match(value)
    if not m:
        raise ValueError(f"invalid card reference '{value}' (expected existing id or 'new')")
    return m.group(1)


def normalize_optional_card_id(value: str, field_name: str) -> str:
    value = strip_ticks(value)
    if not value or value.lower() in {"none", "n/a", "na", "-"}:
        return ""
    m = CARD_ID_RE.match(value)
    if not m:
        raise ValueError(f"invalid {field_name} '{value}' (expected card id or 'none')")
    return m.group(1)


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


def find_card_by_id(card_id: str) -> dict | None:
    for col in ("Backlog", "InProgress", "Blocked", "Done"):
        col_dir = KANBAN_ROOT / col
        if not col_dir.is_dir():
            continue
        for card in col_dir.glob("*.md"):
            try:
                fm, _ = parse_frontmatter(card, required=False)
            except FrontmatterError:
                continue
            if fm.get("id") == card_id:
                return {
                    "id": fm.get("id"),
                    "title": fm.get("title") or card.stem,
                    "type": fm.get("type") or "task",
                    "epic": fm.get("epic") or "",
                    "column": col,
                    "path": str(card),
                }
    return None


def run_kanban_new(*args: str) -> str:
    """Run kanban-new.py and return the new card's id from stdout."""
    result = subprocess.run(
        [sys.executable, str(KANBAN_NEW), *args],
        capture_output=True, text=True, check=True,
    )
    m = re.search(r"^added: \[([\w\d-]+)\]", result.stdout, re.M)
    if not m:
        raise RuntimeError(f"could not parse card id from kanban-new output:\n{result.stdout}")
    return m.group(1)


def run_kanban_set(card_id: str, *args: str) -> None:
    subprocess.run(
        [sys.executable, str(KANBAN_SET), card_id, *args],
        capture_output=True,
        text=True,
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


def open_previous_cards(project: str, prev_sprint: str) -> list[dict]:
    cards: list[dict] = []
    for col in ("Backlog", "InProgress", "Blocked"):
        col_dir = KANBAN_ROOT / col
        if not col_dir.is_dir():
            continue
        for card in col_dir.glob("*.md"):
            try:
                fm, _ = parse_frontmatter(card, required=False)
            except FrontmatterError:
                continue
            if fm.get("project") != project or fm.get("sprint") != prev_sprint:
                continue
            if fm.get("type") == "epic":
                continue
            cards.append({
                "id": fm.get("id") or card.stem,
                "title": fm.get("title") or card.stem,
                "column": col,
            })
    return cards


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
    adopted_cards: list[str] = []
    if not args.no_gate_cards:
        if not gates:
            print(f"  ⚠️ Core Gates에서 추출된 게이트 없음 — gate 카드 발행 skip")
        seen_refs: set[str] = set()
        for gate in gates:
            gid = gate["id"]
            gname = gate["name"]
            try:
                card_ref = normalize_card_ref(gate.get("card") or "")
                source_epic = normalize_optional_card_id(gate.get("source_epic") or "", "source_epic")
            except ValueError as e:
                print(f"  ✗ {gid}: {e}", file=sys.stderr)
                sys.exit(2)
            if source_epic:
                source_card = find_card_by_id(source_epic)
                if not source_card:
                    print(f"  ✗ {gid}: source_epic [{source_epic}] not found", file=sys.stderr)
                    sys.exit(2)
                if source_card["type"] != "epic":
                    print(f"  ✗ {gid}: source_epic [{source_epic}] is not an epic card", file=sys.stderr)
                    sys.exit(2)
            if card_ref and card_ref in seen_refs:
                print(f"  ✗ {gid}: card {card_ref} is mapped to multiple gates", file=sys.stderr)
                sys.exit(2)
            if card_ref:
                seen_refs.add(card_ref)

            existing = find_existing_card(args.project, version, gate=gid)
            if card_ref:
                if existing and existing != card_ref:
                    print(
                        f"  ✗ {gid}: existing sprint card [{existing}] already uses this gate; "
                        f"planning maps [{card_ref}]",
                        file=sys.stderr,
                    )
                    sys.exit(2)
                card_info = find_card_by_id(card_ref)
                if not card_info:
                    print(f"  ✗ {gid}: card [{card_ref}] not found", file=sys.stderr)
                    sys.exit(2)
                if card_info["type"] == "epic":
                    print(
                        f"  ✗ {gid}: card [{card_ref}] is an epic. Split it into smaller gates "
                        f"with `card: new` and `source_epic: {card_ref}`.",
                        file=sys.stderr,
                    )
                    sys.exit(2)
                set_args = ["--project", args.project, "--sprint", version, "--gate", gid]
                if not card_info["epic"] and epic_id:
                    set_args.extend(["--epic", epic_id])
                run_kanban_set(card_ref, *set_args)
                adopted_cards.append(card_ref)
                print(f"    ✓ {gid} 기존 카드 연결: [{card_ref}] {gname}")
                continue

            if existing:
                print(f"    ⤷ {gid} 카드 이미 존재: [{existing}] (skip)")
                continue
            title = f"[{version} {gid}] {gname}"
            new_args = [
                title,
                "--project", args.project,
                "--sprint", version,
                "--gate", gid,
                "--type", "task",
                "--priority", "high",
            ]
            parent_epic = source_epic or epic_id
            if parent_epic:
                new_args.extend(["--epic", parent_epic])
            cid = run_kanban_new(*new_args)
            print(f"    ✓ {gid} 발행: [{cid}] {gname}")

    # Step 3: Carry-over report / legacy sync
    if not args.no_carryover:
        prev = previous_sprint(args.project, version)
        if prev:
            if args.legacy_carryover:
                updated = sync_carryover(args.project, prev, version)
                if updated:
                    print(f"\n  ✓ legacy carry-over: {prev} → {version} 라벨 갱신 {len(updated)}장")
                    for cid in updated:
                        print(f"      [{cid}]")
                else:
                    print(f"\n  ⤷ legacy carry-over: {prev}에 미완료 카드 없음")
            else:
                remaining = open_previous_cards(args.project, prev)
                print(f"\n  ⤷ carry-over: 명시적 card 매핑으로 처리 (adopted {len(adopted_cards)}장)")
                if remaining:
                    print(f"    참고: {prev}에 아직 열린 카드 {len(remaining)}장. 이번 sprint면 planning.md의 `card:`에 매핑하고 재실행하세요.")
                    for card in remaining[:10]:
                        print(f"      [{card['id']}] {card['title']} ({card['column']})")
        else:
            print(f"\n  ⤷ carry-over: 직전 스프린트 없음 (첫 스프린트)")


if __name__ == "__main__":
    main()
