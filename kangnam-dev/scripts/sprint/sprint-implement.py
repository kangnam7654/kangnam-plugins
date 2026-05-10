#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Inspect a sprint plan and produce the implementation dispatch queue.

This script intentionally does not call agents. Slash-command orchestration still
owns dispatch. The script makes the fragile parts deterministic: path/version
normalization, gate parsing, incomplete-gate detection, and card-based done
classification.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _sprint import (  # type: ignore
    normalize_version,
    project_dir,
    sprint_dir,
)
from _agent_kanban import project_working_dir, sprint_cards as load_sprint_cards  # type: ignore


DOMAINS = {"frontend", "backend", "mobile", "data", "devops", "ai"}
SCENARIOS = ("happy", "isolation_failure", "expected_reaction")
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build sprint implementation dispatch queue.")
    p.add_argument("project")
    p.add_argument("version")
    p.add_argument("--parallel", action="store_true", help="Accepted for slash-command orchestration; dispatch is still performed by the command.")
    p.add_argument("--gates", help="Comma-separated gate ids to include, e.g. G1,G3")
    p.add_argument("--working-dir", help="Code directory. Default: ~/projects/<project>")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON only")
    return p.parse_args()


def strip_ticks(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`") and len(value) >= 2:
        return value[1:-1].strip()
    return value


def extract_core_gates_section(text: str) -> str:
    m = re.search(r"^## Core Gates\s*\n(.*?)(?=\n## |\Z)", text, re.S | re.M)
    return m.group(1) if m else ""


def parse_gate_blocks(planning_path: Path) -> list[dict]:
    text = planning_path.read_text(encoding="utf-8")
    section = extract_core_gates_section(text)
    if not section:
        return []

    heading_re = re.compile(r"^###\s+(G\d+)[.\s-]+(.+?)\s*$", re.M)
    hits = list(heading_re.finditer(section))
    gates: list[dict] = []

    for i, hit in enumerate(hits):
        gate_id = hit.group(1)
        heading = hit.group(2).strip()
        start = hit.end()
        end = hits[i + 1].start() if i + 1 < len(hits) else len(section)
        block = section[start:end]
        problems: list[str] = []

        domain = ""
        domain_m = re.search(r"^-\s+\*\*domain\*\*:\s*(.+?)\s*$", block, re.M)
        if domain_m:
            domain = strip_ticks(domain_m.group(1))
        if domain not in DOMAINS:
            problems.append(f"invalid or missing domain: {domain or '(missing)'}")

        scenarios: dict[str, dict] = {}
        for scenario in SCENARIOS:
            desc_m = re.search(
                rf"^-\s+\*\*{re.escape(scenario)}\*\*\s+—\s+(.+?)\s*$",
                block,
                re.M,
            )
            verify_m = None
            if desc_m:
                following = block[desc_m.end():]
                verify_m = re.search(r"^\s+-\s+검증:\s*(.+?)\s*$", following, re.M)

            description = desc_m.group(1).strip() if desc_m else ""
            verification = strip_ticks(verify_m.group(1)) if verify_m else ""
            if not description or description.startswith("<") or "채워주세요" in description:
                problems.append(f"{scenario} description missing or placeholder")
            if not verification or verification.startswith("<") or verification in {"TBD", "TODO", "나중에"}:
                problems.append(f"{scenario} verification missing or placeholder")
            scenarios[scenario] = {
                "description": description,
                "verification": verification,
            }

        if heading.startswith("<") or "채워주세요" in heading:
            problems.append("gate heading is still placeholder")

        gates.append({
            "gate_id": gate_id,
            "heading": heading,
            "domain": domain,
            "scenarios": scenarios,
            "problems": problems,
        })

    return gates


def sprint_cards(project: str, version: str, working_dir: Path) -> list[dict]:
    """Return non-epic kanban cards for project+sprint across active columns."""
    cards: list[dict] = []
    for card in load_sprint_cards(project, version, working_dir, include_done=True):
        if card.get("kind") == "epic":
            continue
        cards.append({
            "id": card.get("id"),
            "title": card.get("title"),
            "gate": card.get("gate") or "",
            "column": card.get("column") or card.get("status"),
            "status": card.get("status"),
            "path": card.get("path"),
        })
    return cards


def cards_by_gate(cards: list[dict]) -> tuple[dict[str, dict], list[dict], list[str]]:
    by_gate: dict[str, dict] = {}
    card_only: list[dict] = []
    duplicate_gates: list[str] = []
    for card in cards:
        gate = card.get("gate") or ""
        if not gate:
            card_only.append(card)
            continue
        if gate in by_gate:
            duplicate_gates.append(gate)
            continue
        by_gate[gate] = card
    return by_gate, card_only, sorted(set(duplicate_gates))


def main() -> None:
    args = parse_args()
    project_dir(args.project)
    version = normalize_version(args.project, args.version)
    working_dir = project_working_dir(args.project, args.working_dir)
    selected = {g.strip() for g in args.gates.split(",")} if args.gates else None

    sd = sprint_dir(args.project, version)
    planning_path = sd / "planning.md"
    if not planning_path.is_file():
        print(f"error: planning.md missing: {planning_path}", file=sys.stderr)
        sys.exit(2)

    all_gates = parse_gate_blocks(planning_path)
    cards = sprint_cards(args.project, version, working_dir)
    gate_to_card, card_only, duplicate_card_gates = cards_by_gate(cards)

    gates = all_gates
    if selected:
        gates = [g for g in all_gates if g["gate_id"] in selected]

    all_gate_ids = {g["gate_id"] for g in all_gates}
    orphan_gate_cards = [
        card for card in cards
        if card.get("gate") and card["gate"] not in all_gate_ids
    ]
    for gate in gates:
        card = gate_to_card.get(gate["gate_id"])
        if card:
            gate["card"] = card
        else:
            gate["card"] = None
            gate["problems"].append("matching kanban card missing; run sprint-publish-cards or label the card with this gate")
        if gate["gate_id"] in duplicate_card_gates:
            gate["problems"].append("multiple kanban cards have this gate; keep exactly one card per gate")

    incomplete = [g for g in gates if g["problems"]]
    dispatch = [
        {
            **g,
            "card_status": (g.get("card") or {}).get("status", "missing"),
        }
        for g in gates
        if not g["problems"] and (g.get("card") or {}).get("status") != "done"
    ]
    skipped_done = [
        {
            "gate_id": g["gate_id"],
            "heading": g["heading"],
            "domain": g["domain"],
            "card": g.get("card"),
        }
        for g in gates
        if not g["problems"] and (g.get("card") or {}).get("status") == "done"
    ]

    report = {
        "project": args.project,
        "version": version,
        "working_dir": str(working_dir),
        "planning_path": str(planning_path),
        "total_gates": len(gates),
        "dispatch_count": len(dispatch),
        "incomplete_count": len(incomplete),
        "skipped_done_count": len(skipped_done),
        "cards_count": len(cards),
        "dispatch": dispatch,
        "incomplete": incomplete,
        "skipped_done": skipped_done,
        "card_only": card_only,
        "orphan_gate_cards": orphan_gate_cards,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(f"\n=== {args.project} {version} 구현 인벤토리 ===")
    print(f"  planning: {planning_path}")
    print(f"  working_dir: {working_dir}")
    print(f"  cards: {len(cards)}")
    print(f"  dispatch 대상: {len(dispatch)} / incomplete: {len(incomplete)} / done skip: {len(skipped_done)}")

    if incomplete:
        print("\nIncomplete gates:")
        for gate in incomplete:
            print(f"  - {gate['gate_id']} {gate['heading']}")
            for problem in gate["problems"]:
                print(f"      * {problem}")

    if dispatch:
        print("\nDispatch queue:")
        for gate in dispatch:
            card = gate.get("card") or {}
            card_label = f"[{card.get('id')}] {card.get('title')}" if card else "(card missing)"
            print(f"  - {gate['gate_id']} {card_label} ({gate['domain']}, {gate['card_status']}) — {gate['heading']}")
    elif not incomplete:
        print("\nDispatch queue empty. All selected gates are done.")

    if card_only:
        print("\nCards without gate labels:")
        for card in card_only:
            print(f"  - [{card['id']}] {card['title']} ({card['column']})")

    if orphan_gate_cards:
        print("\nCards whose gate is not in selected planning gates:")
        for card in orphan_gate_cards:
            print(f"  - [{card['id']}] {card['title']} gate={card['gate']} ({card['column']})")


if __name__ == "__main__":
    main()
