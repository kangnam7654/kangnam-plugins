"""Shared utilities for kanban scripts.

Card files live in column folders under ~/wiki/Kanban/. The folder a file
sits in IS its status, so moving = changing status. Frontmatter holds the
stable id, project, and other metadata.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

KANBAN_ROOT = Path.home() / "wiki" / "Kanban"
COLUMNS = ["Backlog", "InProgress", "Done", "Blocked"]
ALL_FOLDERS = COLUMNS + ["Archive"]
COLUMN_ALIASES = {
    "backlog": "Backlog",
    "todo": "Backlog",
    "inprogress": "InProgress",
    "in-progress": "InProgress",
    "in_progress": "InProgress",
    "doing": "InProgress",
    "wip": "InProgress",
    "done": "Done",
    "complete": "Done",
    "completed": "Done",
    "blocked": "Blocked",
    "block": "Blocked",
    "archive": "Archive",
    "archived": "Archive",
}

ID_PATTERN = re.compile(r"^\d{6}-\d{4}(?:-\d+)?$")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SPRINT_TAG_RE = re.compile(r"^v?\d+\.\d+(?:\.\d+)?(?:[-.]\w+)?$")
SCHEMA_PATH = KANBAN_ROOT / ".schema.json"
BOARD_PATH = KANBAN_ROOT / "BOARD.md"


def fail(msg: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def ensure_initialized() -> None:
    if not KANBAN_ROOT.exists():
        fail(
            f"{KANBAN_ROOT} does not exist. Run kanban-init.py first.",
            code=2,
        )


def normalize_column(name: str) -> str:
    key = name.strip().lower().replace(" ", "")
    if key in COLUMN_ALIASES:
        return COLUMN_ALIASES[key]
    fail(
        f"unknown column '{name}'. Valid: {', '.join(COLUMNS + ['Archive'])}"
    )


def now_iso() -> str:
    """Return current local time as ISO-8601 with timezone offset."""
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def now_id() -> str:
    """Return current time as YYMMDD-HHMM."""
    return dt.datetime.now().strftime("%y%m%d-%H%M")


def slugify(title: str) -> str:
    s = title.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        s = "card"
    return s[:50]


def kebab_safe(slug: str) -> bool:
    return bool(SLUG_PATTERN.match(slug))


@dataclass
class Card:
    path: Path
    frontmatter: dict
    body: str

    @property
    def id(self) -> str:
        return self.frontmatter.get("id", "")

    @property
    def slug(self) -> str:
        return self.path.stem

    @property
    def column(self) -> str:
        return self.path.parent.name

    @property
    def title(self) -> str:
        return self.frontmatter.get("title", self.slug)

    @property
    def project(self) -> str:
        return self.frontmatter.get("project", "")

    @property
    def sprint(self) -> str:
        """Explicit sprint field, or first version-like tag."""
        explicit = self.frontmatter.get("sprint")
        if explicit:
            return str(explicit)
        for t in self.frontmatter.get("tags") or []:
            if SPRINT_TAG_RE.match(str(t)):
                return str(t)
        return ""

    def write(self) -> None:
        write_card(self.path, self.frontmatter, self.body)


def parse_card(path: Path) -> Card:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        fail(f"{path}: missing frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        fail(f"{path}: malformed frontmatter")
    fm = yaml.safe_load(parts[1]) or {}
    body = parts[2].lstrip("\n")
    return Card(path=path, frontmatter=fm, body=body)


def write_card(path: Path, frontmatter: dict, body: str) -> None:
    fm_text = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{fm_text}\n---\n\n{body.lstrip()}", encoding="utf-8")


def iter_cards(columns: Iterable[str] | None = None) -> Iterable[Card]:
    cols = list(columns) if columns else ALL_FOLDERS
    for col in cols:
        folder = KANBAN_ROOT / col
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.md")):
            if p.name.startswith("."):
                continue
            try:
                yield parse_card(p)
            except SystemExit:
                raise
            except Exception as e:
                print(f"warn: failed to parse {p}: {e}", file=sys.stderr)


def find_card(identifier: str) -> Card:
    """Resolve an id (260429-1503) or slug (fix-sync-bug) to a Card."""
    is_id = bool(ID_PATTERN.match(identifier))
    matches: list[Card] = []
    for card in iter_cards():
        if is_id and card.id == identifier:
            matches.append(card)
        elif not is_id and card.slug == identifier:
            matches.append(card)
    if not matches:
        fail(f"no card found for '{identifier}'")
    if len(matches) > 1:
        locs = ", ".join(f"{c.column}/{c.path.name}" for c in matches)
        fail(f"multiple cards match '{identifier}': {locs}. Use the id instead.")
    return matches[0]


def infer_project(explicit: str | None) -> str:
    if explicit:
        return explicit
    cwd = Path.cwd()
    try:
        r = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
            timeout=2,
        )
        url = r.stdout.strip()
        if url:
            tail = url.rstrip("/").split("/")[-1]
            return tail.removesuffix(".git")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    if cwd != Path.home():
        return cwd.name
    fail("could not infer project. Pass --project <name>.")


def load_schema() -> dict:
    if not SCHEMA_PATH.exists():
        return {}
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def regenerate_board() -> None:
    """Invoke kanban-board.py in the same directory."""
    here = Path(__file__).parent
    subprocess.run(
        [sys.executable, str(here / "kanban-board.py")],
        check=False,
    )


def parse_tags(value: str) -> list[str]:
    return [t.strip() for t in value.split(",") if t.strip()]


def short_print(msg: str) -> None:
    print(msg)
