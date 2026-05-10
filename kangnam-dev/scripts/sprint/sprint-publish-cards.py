#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Publish project-local agent-kanban cards for a freshly planned sprint."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _agent_kanban import (  # type: ignore
    ACTIVE_STATUSES,
    create_card,
    find_card_by_id,
    is_epic,
    list_cards,
    project_working_dir,
    set_card_metadata,
    sprint_cards,
    status_label,
)
from _sprint import normalize_version, previous_sprint, project_dir, sprint_dir  # type: ignore


GATE_HEADING_RE = re.compile(
    r"^###\s+(?P<id>G\d+)[.\s\-]+(?P<name>.+?)\s*$",
    re.MULTILINE,
)
CARD_ID_RE = re.compile(r"^\[?(KBN-\d+)\]?$")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Publish epic + gate cards for a sprint using project-local agent-kanban.",
    )
    p.add_argument("project")
    p.add_argument("version")
    p.add_argument("--working-dir", help="Code/project directory whose .kanban board should be used. Default: ~/projects/<project>")
    p.add_argument("--no-epic", action="store_true")
    p.add_argument("--no-gate-cards", action="store_true")
    p.add_argument("--no-carryover", action="store_true")
    p.add_argument(
        "--legacy-carryover",
        action="store_true",
        help="Also relabel all previous sprint open task cards to this sprint. Prefer explicit gate card mappings.",
    )
    return p.parse_args()


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
        raise ValueError(f"invalid card reference '{value}' (expected KBN card id or 'new')")
    return m.group(1)


def normalize_optional_card_id(value: str, field_name: str) -> str:
    value = strip_ticks(value)
    if not value or value.lower() in {"none", "n/a", "na", "-"}:
        return ""
    m = CARD_ID_RE.match(value)
    if not m:
        raise ValueError(f"invalid {field_name} '{value}' (expected KBN card id or 'none')")
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


def find_existing_card(project: str, sprint: str, working_dir: Path, *, gate: str | None = None,
                       card_kind: str | None = None) -> dict | None:
    for card in sprint_cards(project, sprint, working_dir, include_done=True):
        if gate is not None and card.get("gate") != gate:
            continue
        if card_kind == "epic" and card.get("kind") != "epic":
            continue
        if card_kind == "task" and card.get("kind") == "epic":
            continue
        return card
    return None


def sync_carryover(project: str, prev_sprint: str, new_sprint: str, working_dir: Path) -> list[str]:
    updated = []
    for card in list_cards(working_dir, include_done=False):
        if card.get("project") != project or card.get("sprint") != prev_sprint:
            continue
        if card.get("kind") == "epic":
            continue
        if card.get("status") not in ACTIVE_STATUSES:
            continue
        set_card_metadata(card["id"], working_dir, sprint=new_sprint)
        updated.append(card["id"])
    return updated


def open_previous_cards(project: str, prev_sprint: str, working_dir: Path) -> list[dict]:
    cards: list[dict] = []
    for card in list_cards(working_dir, include_done=False):
        if card.get("project") != project or card.get("sprint") != prev_sprint:
            continue
        if card.get("kind") == "epic":
            continue
        if card.get("status") not in ACTIVE_STATUSES:
            continue
        cards.append({
            "id": card.get("id"),
            "title": card.get("title"),
            "column": status_label(card),
        })
    return cards


def main() -> None:
    args = parse_args()
    project_dir(args.project)
    version = normalize_version(args.project, args.version)
    working_dir = project_working_dir(args.project, args.working_dir)
    sd = sprint_dir(args.project, version)
    planning_path = sd / "planning.md"
    if not planning_path.is_file():
        print(f"error: planning.md missing: {planning_path}", file=sys.stderr)
        sys.exit(2)

    summary = extract_one_line_summary(planning_path)
    gates = parse_gates_with_names(planning_path)

    print(f"\n=== {args.project} {version} 카드 발행 ===")
    print(f"  한 줄 요약: {summary or '(비어있음)'}")
    print(f"  Kanban: {working_dir}/.kanban/kanban-data.json")
    print(f"  게이트: {len(gates)}개")
    print()

    epic_id = None
    if not args.no_epic:
        existing_epic = find_existing_card(args.project, version, working_dir, card_kind="epic")
        if existing_epic:
            epic_id = existing_epic["id"]
            print(f"  ⤷ epic 이미 존재: [{epic_id}] (skip)")
        else:
            title = f"[{version}] {summary or '<요약 미기재>'}"
            epic = create_card(
                title,
                working_dir,
                project=args.project,
                kind="epic",
                sprint=version,
                priority="high",
                status="ready",
                next_action="Break down or verify sprint gates.",
            )
            epic_id = epic["id"]
            print(f"  ✓ epic 발행: [{epic_id}]")

    adopted_cards: list[str] = []
    if not args.no_gate_cards:
        if not gates:
            print("  ⚠️ Core Gates에서 추출된 게이트 없음 — gate 카드 발행 skip")
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
                source_card = find_card_by_id(source_epic, working_dir)
                if not source_card:
                    print(f"  ✗ {gid}: source_epic [{source_epic}] not found", file=sys.stderr)
                    sys.exit(2)
                if not is_epic(source_card):
                    print(f"  ✗ {gid}: source_epic [{source_epic}] is not an epic card", file=sys.stderr)
                    sys.exit(2)
            if card_ref and card_ref in seen_refs:
                print(f"  ✗ {gid}: card {card_ref} is mapped to multiple gates", file=sys.stderr)
                sys.exit(2)
            if card_ref:
                seen_refs.add(card_ref)

            existing = find_existing_card(args.project, version, working_dir, gate=gid)
            if card_ref:
                if existing and existing["id"] != card_ref:
                    print(
                        f"  ✗ {gid}: existing sprint card [{existing['id']}] already uses this gate; "
                        f"planning maps [{card_ref}]",
                        file=sys.stderr,
                    )
                    sys.exit(2)
                card_info = find_card_by_id(card_ref, working_dir)
                if not card_info:
                    print(f"  ✗ {gid}: card [{card_ref}] not found", file=sys.stderr)
                    sys.exit(2)
                if is_epic(card_info):
                    print(
                        f"  ✗ {gid}: card [{card_ref}] is an epic. Split it into smaller gates "
                        f"with `card: new` and `source_epic: {card_ref}`.",
                        file=sys.stderr,
                    )
                    sys.exit(2)
                set_card_metadata(
                    card_ref,
                    working_dir,
                    project=args.project,
                    sprint=version,
                    gate=gid,
                    epic_id=card_info.get("epicId") or epic_id,
                )
                adopted_cards.append(card_ref)
                print(f"    ✓ {gid} 기존 카드 연결: [{card_ref}] {gname}")
                continue

            if existing:
                print(f"    ⤷ {gid} 카드 이미 존재: [{existing['id']}] (skip)")
                continue

            parent_epic = source_epic or epic_id
            card = create_card(
                f"[{version} {gid}] {gname}",
                working_dir,
                project=args.project,
                kind="task",
                sprint=version,
                gate=gid,
                epic_id=parent_epic,
                priority="high",
                status="ready",
                next_action=f"Implement and verify sprint gate {gid}.",
            )
            print(f"    ✓ {gid} 발행: [{card['id']}] {gname}")

    if not args.no_carryover:
        prev = previous_sprint(args.project, version)
        if prev:
            if args.legacy_carryover:
                updated = sync_carryover(args.project, prev, version, working_dir)
                if updated:
                    print(f"\n  ✓ legacy carry-over: {prev} → {version} 라벨 갱신 {len(updated)}장")
                    for cid in updated:
                        print(f"      [{cid}]")
                else:
                    print(f"\n  ⤷ legacy carry-over: {prev}에 미완료 카드 없음")
            else:
                remaining = open_previous_cards(args.project, prev, working_dir)
                print(f"\n  ⤷ carry-over: 명시적 card 매핑으로 처리 (adopted {len(adopted_cards)}장)")
                if remaining:
                    print(f"    참고: {prev}에 아직 열린 카드 {len(remaining)}장. 이번 sprint면 planning.md의 `card:`에 매핑하고 재실행하세요.")
                    for card in remaining[:10]:
                        print(f"      [{card['id']}] {card['title']} ({card['column']})")
        else:
            print("\n  ⤷ carry-over: 직전 스프린트 없음 (첫 스프린트)")


if __name__ == "__main__":
    main()
