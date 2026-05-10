"""Small adapter around the packaged project-local agent-kanban CLI."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
AGENT_KANBAN = PLUGIN_ROOT / "scripts" / "agent-kanban" / "agent-kanban.sh"

ACTIVE_STATUSES = ("backlog", "ready", "in_progress", "review", "blocked")
STATUS_LABELS = {
    "backlog": "Backlog",
    "ready": "Ready",
    "in_progress": "InProgress",
    "review": "Review",
    "blocked": "Blocked",
    "done": "Done",
}


def project_working_dir(project: str, value: str | None = None) -> Path:
    return Path(value).expanduser().resolve() if value else (Path.home() / "projects" / project)


def run_agent_kanban(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(AGENT_KANBAN), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def kanban_data_path(working_dir: Path) -> str:
    return run_agent_kanban("path", "--cwd", str(working_dir)).stdout.strip()


def list_cards(working_dir: Path, *, include_done: bool = True) -> list[dict]:
    args = ["list", "--cwd", str(working_dir), "--json", "--limit", "200"]
    if include_done:
        args.append("--include-done")
    page = json.loads(run_agent_kanban(*args).stdout)
    return page.get("cards") or []


def card_ref(card: dict, working_dir: Path) -> str:
    return f"{kanban_data_path(working_dir)}#cards/{card.get('id')}"


def sprint_cards(project: str, version: str, working_dir: Path, *, include_done: bool = True) -> list[dict]:
    cards: list[dict] = []
    for card in list_cards(working_dir, include_done=include_done):
        if card.get("project") != project:
            continue
        if card.get("sprint") != version:
            continue
        enriched = dict(card)
        enriched["column"] = status_label(enriched)
        enriched["path"] = card_ref(enriched, working_dir)
        cards.append(enriched)
    return cards


def find_card_by_id(card_id: str, working_dir: Path) -> dict | None:
    for card in list_cards(working_dir, include_done=True):
        if card.get("id") == card_id:
            enriched = dict(card)
            enriched["column"] = status_label(enriched)
            enriched["path"] = card_ref(enriched, working_dir)
            return enriched
    return None


def create_card(
    title: str,
    working_dir: Path,
    *,
    project: str,
    kind: str,
    sprint: str | None = None,
    gate: str | None = None,
    epic_id: str | None = None,
    priority: str = "high",
    status: str = "ready",
    description: str | None = None,
    next_action: str | None = None,
) -> dict:
    args = [
        "create", title,
        "--cwd", str(working_dir),
        "--json",
        "--type", kind,
        "--project", project,
        "--priority", priority,
        "--status", status,
    ]
    if sprint:
        args.extend(["--sprint", sprint])
    if gate:
        args.extend(["--gate", gate])
    if epic_id:
        args.extend(["--epic", epic_id])
    if description:
        args.extend(["--desc", description])
    if next_action:
        args.extend(["--next", next_action])
    return json.loads(run_agent_kanban(*args).stdout)


def set_card_metadata(
    card_id: str,
    working_dir: Path,
    *,
    project: str | None = None,
    sprint: str | None = None,
    gate: str | None = None,
    epic_id: str | None = None,
) -> dict:
    args = ["set", card_id, "--cwd", str(working_dir), "--json"]
    if project is not None:
        args.extend(["--project", project])
    if sprint is not None:
        args.extend(["--sprint", sprint])
    if gate is not None:
        args.extend(["--gate", gate])
    if epic_id is not None:
        args.extend(["--epic", epic_id])
    return json.loads(run_agent_kanban(*args).stdout)


def status_label(card: dict) -> str:
    return STATUS_LABELS.get(str(card.get("status") or ""), str(card.get("status") or ""))


def is_epic(card: dict) -> bool:
    return card.get("kind") == "epic"
