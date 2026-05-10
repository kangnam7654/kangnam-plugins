"""Shared utilities for sprint-* scripts.

Sprints live at ~/wiki/Projects/<project>/Sprints/<version>/{planning,review}.md.
Gate execution state lives in the project-local `.kanban/kanban-data.json`.
The folder name is the version label. Project-level convention determines whether
versions carry a 'v' prefix (e.g., dear-jeongbin uses v0.1.0; auto_company uses 0.0.1).
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

import yaml

WIKI_ROOT = Path.home() / "wiki"
PROJECTS_ROOT = WIKI_ROOT / "Projects"
RETRO_REGULAR = WIKI_ROOT / "Retro" / "regular"

VERSION_RE = re.compile(r"^v?\d+\.\d+(?:\.\d+)?(?:[-.]\w+)?$")
SEMVER_PARTS_RE = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?(?:[-.](\w+))?$")


def fail(msg: str, code: int = 1) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def today() -> str:
    return dt.date.today().isoformat()


def now_iso() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def ensure_wiki_clean_and_pulled() -> None:
    """Pull wiki with rebase. Refuse if dirty."""
    status = subprocess.run(
        ["git", "-C", str(WIKI_ROOT), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    if status.strip():
        fail(
            f"wiki has uncommitted changes. Resolve first:\n{status}",
            code=3,
        )
    subprocess.run(
        ["git", "-C", str(WIKI_ROOT), "pull", "--rebase"],
        check=True,
    )


def project_dir(project: str) -> Path:
    p = PROJECTS_ROOT / project
    if not p.is_dir():
        fail(
            f"project folder not found: {p}\n"
            f"Create it first or check the project name (case-sensitive).",
            code=2,
        )
    return p


def sprints_dir(project: str) -> Path:
    return project_dir(project) / "Sprints"


def sprint_dir(project: str, version: str) -> Path:
    return sprints_dir(project) / version


def project_uses_v_prefix(project: str) -> bool | None:
    """Detect whether a project's existing sprints use 'v' prefix.

    Returns None if no existing sprints (caller decides).
    """
    sd = sprints_dir(project)
    if not sd.is_dir():
        return None
    versions = [d.name for d in sd.iterdir() if d.is_dir()]
    if not versions:
        return None
    v_count = sum(1 for v in versions if v.startswith("v"))
    plain_count = sum(1 for v in versions if SEMVER_PARTS_RE.match(v) and not v.startswith("v"))
    if v_count == plain_count == 0:
        return None
    return v_count >= plain_count


def normalize_version(project: str, version: str) -> str:
    """Apply project's v-prefix convention to user-supplied version."""
    if not VERSION_RE.match(version):
        fail(
            f"invalid version format: '{version}'. "
            f"Expected SemVer like 0.0.6 or v0.1.0 or v0.0.2-alpha.",
            code=2,
        )
    uses_v = project_uses_v_prefix(project)
    if uses_v is None:
        # No precedent — accept as-is
        return version
    has_v = version.startswith("v")
    if uses_v and not has_v:
        return "v" + version
    if not uses_v and has_v:
        return version[1:]
    return version


def semver_sort_key(version: str) -> tuple:
    m = SEMVER_PARTS_RE.match(version)
    if not m:
        return (-1, -1, -1, version)
    major, minor, patch, suffix = m.groups()
    return (
        int(major),
        int(minor),
        int(patch) if patch else 0,
        suffix or "",
    )


def list_sprints(project: str) -> list[str]:
    sd = sprints_dir(project)
    if not sd.is_dir():
        return []
    return sorted(
        [d.name for d in sd.iterdir() if d.is_dir()],
        key=semver_sort_key,
    )


def previous_sprint(project: str, current: str) -> str | None:
    """Return the sprint directly before `current` (semver-sorted), or None."""
    versions = list_sprints(project)
    if current not in versions:
        # current is new — last existing is the previous
        return versions[-1] if versions else None
    idx = versions.index(current)
    return versions[idx - 1] if idx > 0 else None


class FrontmatterError(Exception):
    """Frontmatter is malformed or missing — never silently fall back."""


def parse_frontmatter(path: Path, *, required: bool = True) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_str).

    If required=True (default) and frontmatter is missing or malformed, raise
    FrontmatterError instead of returning empty dict — silent fallback hides
    user-visible bugs (status check passes when the file has no status at all).
    """
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if not m:
        if required:
            raise FrontmatterError(
                f"{path} has no YAML frontmatter (--- ... --- block at top). "
                f"Cannot determine status/sprint/project. Fix the file before retry."
            )
        return ({}, text)
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise FrontmatterError(f"{path} has malformed YAML frontmatter: {e}") from e
    if required and not isinstance(fm, dict):
        raise FrontmatterError(f"{path} frontmatter is not a YAML mapping.")
    body = text[m.end():]
    return (fm, body)


def write_with_frontmatter(path: Path, fm: dict, body: str) -> None:
    fm_text = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).rstrip()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{fm_text}\n---\n\n{body.lstrip()}", encoding="utf-8")


ACTION_ITEMS_HEADING_RE = re.compile(
    r"^##\s*(?:[✅✨\U0001F4CC\U0001F4DD⚡]\s*)?Action[\s_-]*Items?\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
CORE_GATES_HEADING_RE = re.compile(
    r"^##\s*(?:[✅✨\U0001F510\U0001F6AA]\s*)?Core[\s_-]*Gates?\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
GATE_HEADING_RE = re.compile(r"^###\s+(?:G[-\s]*\d+|Gate\s*\d+)\b", re.IGNORECASE)


def _extract_section(text: str, heading_re: re.Pattern) -> str | None:
    """Return body of the first matching ## heading, up to next ## or EOF."""
    m = heading_re.search(text)
    if not m:
        return None
    rest = text[m.end():]
    next_h = re.search(r"^## ", rest, re.MULTILINE)
    return rest[: next_h.start()] if next_h else rest


def extract_action_items(review_path: Path) -> list[str]:
    """Extract Action Items bullets from a review.md file. Heading match is
    case-insensitive and tolerates emoji/punctuation prefix variations."""
    if not review_path.is_file():
        return []
    text = review_path.read_text(encoding="utf-8")
    section = _extract_section(text, ACTION_ITEMS_HEADING_RE)
    if section is None:
        return []
    items = []
    for line in section.splitlines():
        s = line.strip()
        if s.startswith("- "):
            items.append(s)
    return items


def extract_core_gates(planning_path: Path) -> list[str]:
    """Extract gate headings (### G1., ### Gate 1, ### G-1) from planning.md."""
    if not planning_path.is_file():
        return []
    text = planning_path.read_text(encoding="utf-8")
    section = _extract_section(text, CORE_GATES_HEADING_RE)
    if section is None:
        return []
    return [
        line.strip()
        for line in section.splitlines()
        if GATE_HEADING_RE.match(line)
    ]


def confirm_overwrite(path: Path, *, force: bool = False) -> bool:
    """Return True to proceed. Refuses by default if path exists."""
    if not path.exists():
        return True
    if force:
        return True
    fail(
        f"{path} already exists. Use --force to overwrite.",
        code=4,
    )


def git_add(*paths: Path) -> None:
    rels = [str(p.relative_to(WIKI_ROOT)) for p in paths if p.exists()]
    if not rels:
        return
    subprocess.run(["git", "-C", str(WIKI_ROOT), "add", *rels], check=True)


def git_commit(message: str) -> bool:
    """Commit if anything is staged. Returns True if committed."""
    diff = subprocess.run(
        ["git", "-C", str(WIKI_ROOT), "diff", "--cached", "--quiet"],
    )
    if diff.returncode == 0:
        return False  # nothing staged
    subprocess.run(
        ["git", "-C", str(WIKI_ROOT), "commit", "-m", message],
        check=True,
    )
    return True
