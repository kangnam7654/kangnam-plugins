#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Initialize ~/wiki/Kanban/ with column folders, schema, and empty BOARD.md."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _kanban import ALL_FOLDERS, BOARD_PATH, KANBAN_ROOT, SCHEMA_PATH

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Kanban Card Frontmatter",
    "type": "object",
    "required": ["id", "title", "project", "created"],
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string", "pattern": "^[0-9]{6}-[0-9]{4}(?:-[0-9]+)?$"},
        "title": {"type": "string", "minLength": 1},
        "project": {"type": "string", "minLength": 1},
        "created": {"type": "string"},
        "sprint": {"type": "string"},
        "priority": {"enum": ["high", "med", "low"]},
        "tags": {"type": "array", "items": {"type": "string"}},
        "due": {"type": "string"},
        "type": {"enum": ["epic", "task"]},
        "epic": {"type": "string", "pattern": "^[0-9]{6}-[0-9]{4}(?:-[0-9]+)?$"},
        "gate": {"type": "string", "pattern": "^G[0-9]+$"},
        "blocked_by": {"type": "string", "pattern": "^[0-9]{6}-[0-9]{4}(?:-[0-9]+)?$"},
        "completed_at": {"type": "string"},
    },
}


def main() -> None:
    KANBAN_ROOT.mkdir(parents=True, exist_ok=True)
    for folder in ALL_FOLDERS:
        d = KANBAN_ROOT / folder
        d.mkdir(exist_ok=True)
        gitkeep = d / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()

    if not SCHEMA_PATH.exists():
        SCHEMA_PATH.write_text(
            json.dumps(SCHEMA, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if not BOARD_PATH.exists():
        BOARD_PATH.write_text(
            "# Kanban Board\n\n"
            "> Empty board. Create your first card with `kanban-new.py`.\n",
            encoding="utf-8",
        )

    print(f"initialized: {KANBAN_ROOT}")
    for folder in ALL_FOLDERS:
        print(f"  {folder}/")
    print(f"  BOARD.md")
    print(f"  .schema.json")


if __name__ == "__main__":
    main()
