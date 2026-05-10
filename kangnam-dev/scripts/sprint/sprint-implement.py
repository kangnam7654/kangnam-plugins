#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Inspect a sprint plan and produce the implementation dispatch queue.

This script intentionally does not call agents. Slash-command orchestration still
owns dispatch. The script makes the fragile parts deterministic: path/version
normalization, progress.md scaffolding, gate parsing, incomplete-gate detection,
and done/partial/pending classification.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _sprint import (  # type: ignore
    WIKI_ROOT,
    FrontmatterError,
    normalize_version,
    parse_frontmatter,
    project_dir,
    sprint_dir,
)


DOMAINS = {"frontend", "backend", "mobile", "data", "devops", "ai"}
SCENARIOS = ("happy", "isolation_failure", "expected_reaction")
KANBAN_COLUMNS = ("Backlog", "InProgress", "Blocked", "Done")


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


def scaffold_progress(project: str, version: str, progress_path: Path) -> None:
    if progress_path.is_file():
        return
    script = Path(__file__).parent / "sprint-progress.py"
    subprocess.run(
        [sys.executable, str(script), project, version],
        check=True,
        capture_output=True,
        text=True,
    )


def progress_gate_status(progress_path: Path) -> dict[str, str]:
    if not progress_path.is_file():
        return {}
    text = progress_path.read_text(encoding="utf-8")
    m = re.search(r"^## 게이트\s*\n(.*?)(?=\n## |\Z)", text, re.S | re.M)
    if not m:
        return {}
    section = m.group(1)
    heading_re = re.compile(r"^###\s+(G\d+)\b.*$", re.M)
    hits = list(heading_re.finditer(section))
    out: dict[str, str] = {}
    for i, hit in enumerate(hits):
        gate_id = hit.group(1)
        start = hit.end()
        end = hits[i + 1].start() if i + 1 < len(hits) else len(section)
        block = section[start:end]
        checks = re.findall(r"^-\s+\[([ x])\]\s+\*\*(happy|isolation_failure|expected_reaction)\*\*\s+—\s+(.+?)$", block, re.M)
        if len(checks) < 3:
            out[gate_id] = "pending"
            continue
        checked = [mark == "x" and "<검증 메모" not in memo and "manual verification required" not in memo for mark, _, memo in checks]
        if all(checked):
            out[gate_id] = "done"
        elif any(checked):
            out[gate_id] = "partial"
        else:
            out[gate_id] = "pending"
    return out


def sprint_cards(project: str, version: str) -> list[dict]:
    """Return non-epic kanban cards for project+sprint across active columns."""
    cards: list[dict] = []
    root = WIKI_ROOT / "Kanban"
    if not root.is_dir():
        return cards
    for column in KANBAN_COLUMNS:
        col_dir = root / column
        if not col_dir.is_dir():
            continue
        for path in sorted(col_dir.glob("*.md")):
            try:
                fm, _ = parse_frontmatter(path, required=False)
            except FrontmatterError:
                continue
            if fm.get("project") != project or fm.get("sprint") != version:
                continue
            if fm.get("type") == "epic":
                continue
            cards.append({
                "id": fm.get("id") or path.stem,
                "title": fm.get("title") or path.stem,
                "gate": fm.get("gate") or "",
                "column": column,
                "path": str(path),
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
    working_dir = Path(args.working_dir).expanduser() if args.working_dir else Path.home() / "projects" / args.project
    selected = {g.strip() for g in args.gates.split(",")} if args.gates else None

    sd = sprint_dir(args.project, version)
    planning_path = sd / "planning.md"
    progress_path = sd / "progress.md"
    if not planning_path.is_file():
        print(f"error: planning.md missing: {planning_path}", file=sys.stderr)
        sys.exit(2)

    scaffold_progress(args.project, version, progress_path)
    all_gates = parse_gate_blocks(planning_path)
    statuses = progress_gate_status(progress_path)
    cards = sprint_cards(args.project, version)
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
            "progress_status": statuses.get(g["gate_id"], "pending"),
        }
        for g in gates
        if not g["problems"] and statuses.get(g["gate_id"], "pending") != "done"
    ]
    skipped_done = [
        {
            "gate_id": g["gate_id"],
            "heading": g["heading"],
            "domain": g["domain"],
        }
        for g in gates
        if not g["problems"] and statuses.get(g["gate_id"], "pending") == "done"
    ]

    report = {
        "project": args.project,
        "version": version,
        "working_dir": str(working_dir),
        "planning_path": str(planning_path),
        "progress_path": str(progress_path),
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
    print(f"  progress: {progress_path}")
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
            print(f"  - {gate['gate_id']} {card_label} ({gate['domain']}, {gate['progress_status']}) — {gate['heading']}")
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
