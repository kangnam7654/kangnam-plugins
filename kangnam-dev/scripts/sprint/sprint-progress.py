#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Scaffold or freeze a sprint's progress.md.

Usage:
  sprint-progress.py <project> <version>           # scaffold/inspect
  sprint-progress.py <project> <version> --freeze  # validate + freeze

What it does (safe / structured parts):
- Validates planning.md exists
- Creates progress.md skeleton from planning.md's Core Gates if missing
- Reports current gate completion + Kanban card alignment
- --freeze: validates all gates ✅ + flips status to evergreen

It does NOT:
- Decide which gates passed (AI / user updates checkboxes)
- Generate verification log entries (caller fills in)
- Push (NEVER)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _sprint import (  # type: ignore
    WIKI_ROOT,
    FrontmatterError,
    extract_core_gates,
    git_add,
    normalize_version,
    parse_frontmatter,
    project_dir,
    sprint_dir,
    today,
    write_with_frontmatter,
)
from _agent_kanban import AGENT_KANBAN, project_working_dir, sprint_cards as load_sprint_cards  # type: ignore

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scaffold/freeze sprint progress.md.")
    p.add_argument("project")
    p.add_argument("version")
    p.add_argument("--freeze", action="store_true", help="Freeze sprint (status: evergreen)")
    p.add_argument("--force", action="store_true", help="Force freeze even with unchecked gates")
    p.add_argument("--working-dir", help="Code/project directory whose .kanban board should be used. Default: ~/projects/<project>")
    return p.parse_args()


PROGRESS_TEMPLATE = """\
# {project} — {version} Readiness Gates (DRAFT)

> 아직 closed 아님. 게이트별로 happy/isolation_failure/expected_reaction 모두 검증돼야 evergreen 동결. 룰: [[../../../../Rules/SprintReadiness]].

## 게이트

{gate_blocks}

## 검증 로그

| 날짜 | 게이트 | 결과 | 메모 |
|---|---|---|---|

## Out-of-scope (이번 사이클 deferred)

<deferred로 보낸 항목들 — `deferred.md`와 sync>
"""


def build_gate_blocks(gates: list[str]) -> str:
    if not gates:
        return "### G1. <게이트 이름>\n- [ ] **happy** — <검증 메모, 날짜>\n- [ ] **isolation_failure** — <검증 메모, 날짜>\n- [ ] **expected_reaction** — <검증 메모, 날짜>\n\n### G2. ..."
    blocks = []
    for g in gates:
        blocks.append(
            f"{g}\n"
            f"- [ ] **happy** — <검증 메모, 날짜>\n"
            f"- [ ] **isolation_failure** — <검증 메모, 날짜>\n"
            f"- [ ] **expected_reaction** — <검증 메모, 날짜>"
        )
    return "\n\n".join(blocks)


DATE_RE = re.compile(r"(?<![\d-])\d{4}-\d{2}-\d{2}(?![\d-])")
PLACEHOLDER_FRAGMENTS = ("검증 메모, 날짜>", "<검증", "**채워주세요**", "TODO", "TBD")
MEMO_MIN_CHARS = 20  # 게이트 검증 메모 최소 길이 (체크박스/볼드 제외)


def count_gate_progress(progress_path: Path) -> tuple[int, int, list[str]]:
    """Return (checked, total, problems) by scanning checkboxes in 게이트 section.

    A checked line is reported as a 'problem' if any of:
    - placeholder fragment still present
    - no ISO date (YYYY-MM-DD) in the line
    - memo text (after `— `) shorter than MEMO_MIN_CHARS

    No fallback: if the file has no 게이트 section, return (0, 0, []) so the
    caller surfaces the missing structure rather than silently passing.
    """
    text = progress_path.read_text(encoding="utf-8")
    m = re.search(r"^## 게이트\s*\n(.*?)(?=\n## |\Z)", text, re.S | re.M)
    if not m:
        return (0, 0, [])
    section = m.group(1)
    checked = len(re.findall(r"^- \[x\]", section, re.M))
    total = len(re.findall(r"^- \[[ x]\]", section, re.M))
    problems: list[str] = []
    for line in section.splitlines():
        if not re.match(r"^- \[x\]", line):
            continue
        s = line.strip()
        if any(frag in s for frag in PLACEHOLDER_FRAGMENTS):
            problems.append(s)
            continue
        if not DATE_RE.search(s):
            problems.append(s)
            continue
        memo_part = s.split("—", 1)[-1] if "—" in s else s
        memo_clean = re.sub(r"_?\d{4}-\d{2}-\d{2}.*$", "", memo_part).strip()
        if len(memo_clean) < MEMO_MIN_CHARS:
            problems.append(s)
    return (checked, total, problems)


def kanban_cards_for_sprint(project: str, version: str, working_dir: Path) -> dict[str, list[dict]]:
    """Return cards by column for this sprint.
    Each card dict: {id, title, gate, type}. `gate` may be empty string.
    """
    result: dict[str, list[dict]] = {"Ready": [], "InProgress": [], "Review": [], "Done": [], "Backlog": [], "Blocked": []}
    for card in load_sprint_cards(project, version, working_dir, include_done=True):
        col = card.get("column") or card.get("status") or ""
        result.setdefault(col, []).append({
            "id": card.get("id"),
            "title": card.get("title"),
            "gate": card.get("gate") or "",
            "type": card.get("kind") or "task",
            "status": card.get("status") or "",
        })
    return result


def gate_check_status(progress_path: Path) -> dict[str, bool]:
    """Return {G1: True, G2: False, ...} — True if ALL three checkboxes ([happy/isolation/expected]) under that gate are [x]."""
    text = progress_path.read_text(encoding="utf-8")
    m = re.search(r"^## 게이트\s*\n(.*?)(?=\n## |\Z)", text, re.S | re.M)
    if not m:
        return {}
    section = m.group(1)
    out: dict[str, bool] = {}
    current_gate: str | None = None
    counters: dict[str, list[bool]] = {}
    for line in section.splitlines():
        gh = re.match(r"^###\s+(G\d+)\b", line)
        if gh:
            current_gate = gh.group(1)
            counters.setdefault(current_gate, [])
            continue
        if current_gate is None:
            continue
        cb = re.match(r"^- \[([ x])\]", line)
        if cb:
            counters[current_gate].append(cb.group(1) == "x")
    for g, checks in counters.items():
        out[g] = bool(checks) and all(checks)
    return out


def alignment_warnings(
    progress_path: Path, cards_by_col: dict[str, list[dict]], working_dir: Path,
) -> list[str]:
    """Compare progress.md gate status vs gate-card columns.

    Two kinds of mismatch:
    1. gate ✅ but gate-card not in Done → "move card to Done"
    2. gate-card in Done but gate is [ ] → "fill verification memo"
    """
    gate_status = gate_check_status(progress_path)
    if not gate_status:
        return []

    # Build map: gate -> (column, card)
    gate_to_card: dict[str, tuple[str, dict]] = {}
    for col, cards in cards_by_col.items():
        for c in cards:
            if c["type"] == "epic":
                continue
            g = c.get("gate")
            if g:
                gate_to_card[g] = (col, c)

    warnings: list[str] = []
    for gate, passed in gate_status.items():
        match = gate_to_card.get(gate)
        if not match:
            continue
        col, card = match
        if passed and col != "Done":
            warnings.append(
                f"  ⚠️ 게이트 {gate} ✅ 검증 완료, 그러나 카드 [{card['id']}]는 {col}.\n"
                f"      → {AGENT_KANBAN} done {card['id']} --cwd {working_dir} --summary \"{gate} 검증 완료\""
            )
        elif (not passed) and col == "Done":
            warnings.append(
                f"  ⚠️ 카드 [{card['id']}]는 Done, 그러나 게이트 {gate}는 [ ] (검증 메모 누락).\n"
                f"      → progress.md에서 {gate} 검증 메모를 채우세요."
            )
    return warnings


def freeze(progress_path: Path, force: bool) -> None:
    try:
        fm, body = parse_frontmatter(progress_path)
    except FrontmatterError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    checked, total, problems = count_gate_progress(progress_path)
    if total == 0:
        print(f"error: no gate checkboxes found in {progress_path}", file=sys.stderr)
        print("       (Core Gates section may be missing or use unrecognized heading)", file=sys.stderr)
        sys.exit(2)
    if checked < total and not force:
        print(f"error: {total - checked}/{total} gates unchecked. Use --force to freeze anyway.", file=sys.stderr)
        sys.exit(2)
    if problems and not force:
        print(
            f"error: {len(problems)} checked gate(s) fail validation "
            f"(placeholder text, missing date YYYY-MM-DD, or memo < {MEMO_MIN_CHARS} chars).",
            file=sys.stderr,
        )
        for p in problems[:5]:
            print(f"  {p}", file=sys.stderr)
        print("       Fix each verification memo (must include date + ≥20 char description), then retry.", file=sys.stderr)
        sys.exit(2)

    fm["status"] = "evergreen"
    fm["updated"] = today()
    # Update title from DRAFT to CLOSED if present
    body = re.sub(r"(# .+ Readiness Gates) \(DRAFT\)", r"\1 (CLOSED)", body)
    body = re.sub(r"^> 아직 closed 아님.*$", f"> **{progress_path.parent.name} 출시 동결 ({today()}).** 모든 게이트 검증 완료.", body, count=1, flags=re.M)

    write_with_frontmatter(progress_path, fm, body)
    git_add(progress_path)
    print(f"✓ frozen: {progress_path}")
    print(f"  ({checked}/{total} gates)")


def report(progress_path: Path, project: str, version: str, working_dir: Path) -> None:
    try:
        fm, _ = parse_frontmatter(progress_path)
    except FrontmatterError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    if "status" not in fm:
        print(f"error: {progress_path} frontmatter has no 'status' field.", file=sys.stderr)
        sys.exit(2)
    status = fm["status"]
    checked, total, problems = count_gate_progress(progress_path)
    cards = kanban_cards_for_sprint(project, version, working_dir)

    print(f"\n=== {project} {version} 진행 상황 ===")
    print(f"  파일: {progress_path}")
    print(f"  Kanban: {working_dir}/.kanban/kanban-data.json")
    print(f"  상태: {status}")
    print(f"  게이트: {checked}/{total} ✅")
    if problems:
        print(f"  ⚠️  검증 부실한 [x] 게이트 {len(problems)}건 (placeholder/날짜 누락/메모 부족) — 동결 시 거부됨")
    print()
    print(f"  Kanban (sprint={version}):")
    for col in ("InProgress", "Ready", "Review", "Backlog", "Done", "Blocked"):
        if not cards.get(col):
            continue
        print(f"    {col}: {len(cards[col])}")
        for c in cards[col][:5]:
            gate_tag = f" [{c['gate']}]" if c.get("gate") else ""
            type_tag = " (epic)" if c.get("type") == "epic" else ""
            print(f"      -{gate_tag}{type_tag} {c['title']}")

    warnings = alignment_warnings(progress_path, cards, working_dir)
    if warnings:
        print()
        print(f"  🔔 게이트-카드 정합성 경고 {len(warnings)}건:")
        for w in warnings:
            print(w)

    if status == "evergreen":
        print()
        print(f"  ▶ 동결됨. 회고: /kangnam-dev:sprint-review {project} {version}")
    elif checked == total and total > 0:
        print()
        print(f"  ▶ 모든 게이트 ✅ — 동결 가능: --freeze 추가")


def main() -> None:
    args = parse_args()
    project_dir(args.project)
    version = normalize_version(args.project, args.version)
    working_dir = project_working_dir(args.project, args.working_dir)
    sd = sprint_dir(args.project, version)
    planning_path = sd / "planning.md"
    progress_path = sd / "progress.md"

    if not planning_path.is_file():
        print(f"error: planning.md missing. Run sprint-planning first: {planning_path}", file=sys.stderr)
        sys.exit(2)

    if not progress_path.is_file():
        gates = extract_core_gates(planning_path)
        fm = {
            "created": today(),
            "updated": today(),
            "type": "project_spec",
            "status": "growing",
            "project": args.project,
            "sprint": version,
        }
        body = PROGRESS_TEMPLATE.format(
            project=args.project,
            version=version,
            gate_blocks=build_gate_blocks(gates),
        )
        write_with_frontmatter(progress_path, fm, body)
        git_add(progress_path)
        print(f"✓ scaffolded: {progress_path}")
        if gates:
            print(f"  ({len(gates)} gates extracted from planning.md)")
        else:
            print(f"  (no Core Gates found in planning.md — using template skeleton)")
        print(f"\nEdit progress.md as gates are verified. Use --freeze to close.")
        return

    if args.freeze:
        freeze(progress_path, args.force)
    else:
        report(progress_path, args.project, version, working_dir)


if __name__ == "__main__":
    main()
