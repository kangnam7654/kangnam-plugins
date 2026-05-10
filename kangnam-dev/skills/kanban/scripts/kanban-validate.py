#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Validate every card's frontmatter against .schema.json. Exit 1 on errors."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _kanban import (
    ALL_FOLDERS,
    KANBAN_ROOT,
    SCHEMA_PATH,
    ensure_initialized,
    iter_cards,
)


COMPAT_PROPS = {
    "id": {"type": "string", "pattern": "^[0-9]{6}-[0-9]{4}(?:-[0-9]+)?$"},
    "sprint": {"type": "string"},
    "gate": {"type": "string", "pattern": "^G[0-9]+$"},
    "epic": {"type": "string", "pattern": "^[0-9]{6}-[0-9]{4}(?:-[0-9]+)?$"},
    "blocked_by": {"type": "string", "pattern": "^[0-9]{6}-[0-9]{4}(?:-[0-9]+)?$"},
}


def normalize_schema(schema: dict) -> dict:
    """Tolerate older .schema.json files created before sprint/gate metadata."""
    props = schema.setdefault("properties", {})
    for key, spec in COMPAT_PROPS.items():
        props[key] = spec
    return schema


def validate_card(fm: dict, schema: dict) -> list[str]:
    errors: list[str] = []
    required = schema.get("required", [])
    props = schema.get("properties", {})
    additional = schema.get("additionalProperties", True)

    for field in required:
        if field not in fm:
            errors.append(f"missing required field: {field}")

    for key, value in fm.items():
        if key not in props:
            if additional is False:
                errors.append(f"unknown field: {key}")
            continue
        spec = props[key]
        if "enum" in spec and value not in spec["enum"]:
            errors.append(f"{key}: '{value}' not in {spec['enum']}")
        elif "type" in spec:
            t = spec["type"]
            if t == "string" and not isinstance(value, str):
                errors.append(f"{key}: expected string, got {type(value).__name__}")
            elif t == "array" and not isinstance(value, list):
                errors.append(f"{key}: expected array, got {type(value).__name__}")
            elif t == "object" and not isinstance(value, dict):
                errors.append(f"{key}: expected object, got {type(value).__name__}")
        if "pattern" in spec and isinstance(value, str):
            if not re.match(spec["pattern"], value):
                errors.append(f"{key}: '{value}' does not match {spec['pattern']}")
        if "minLength" in spec and isinstance(value, str):
            if len(value) < spec["minLength"]:
                errors.append(f"{key}: too short (min {spec['minLength']})")
    return errors


def main() -> None:
    ensure_initialized()
    if not SCHEMA_PATH.exists():
        print(f"warn: {SCHEMA_PATH} missing — run kanban-init.py", file=sys.stderr)
        sys.exit(1)
    schema = normalize_schema(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))

    total = 0
    bad = 0
    by_id: dict[str, list] = {}
    by_slug: dict[str, list] = {}
    for card in iter_cards(ALL_FOLDERS):
        total += 1
        errors = validate_card(card.frontmatter, schema)
        if card.column == "Done" and "completed_at" not in card.frontmatter:
            errors.append("Done card missing completed_at")
        if card.column == "Blocked" and "blocked_by" not in card.frontmatter:
            # warn-level: blocked_by is recommended but not required
            print(f"warn: {card.path}: Blocked card missing blocked_by", file=sys.stderr)
        # Archive holds removed/duplicate cards — exclude from active uniqueness checks.
        if card.column != "Archive":
            by_id.setdefault(card.id, []).append(card)
            by_slug.setdefault(card.slug, []).append(card)
        if errors:
            bad += 1
            rel = card.path.relative_to(KANBAN_ROOT)
            for e in errors:
                print(f"FAIL {rel}: {e}")

    # Cross-column duplicate detection: a card id (or slug) must live in exactly one column.
    dup_count = 0
    for cid, cards in by_id.items():
        if len(cards) > 1:
            dup_count += 1
            locs = ", ".join(f"{c.column}/{c.path.name}" for c in cards)
            print(f"FAIL duplicate id '{cid}': {locs}")
    for slug, cards in by_slug.items():
        if len(cards) > 1 and len({c.id for c in cards}) > 1:
            # same slug across cards with different ids — warn (likely a kanban-new collision)
            locs = ", ".join(f"{c.column}/{c.path.name}[{c.id}]" for c in cards)
            print(f"warn: slug '{slug}' shared by multiple ids: {locs}", file=sys.stderr)

    if bad or dup_count:
        if bad:
            print(f"\n{bad}/{total} cards failed validation", file=sys.stderr)
        if dup_count:
            print(f"{dup_count} cross-column duplicate id(s) found", file=sys.stderr)
        sys.exit(1)
    print(f"OK: {total} cards valid")


if __name__ == "__main__":
    main()
