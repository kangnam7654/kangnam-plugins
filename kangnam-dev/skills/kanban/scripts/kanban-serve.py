#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Live local web viewer for ~/wiki/Kanban/ with drag-drop column moves.

Mutations always shell out to kanban-move.py — never touch card files directly.
Bind defaults to 127.0.0.1 only; pass --allow-lan to bind 0.0.0.0.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _kanban import (
    COLUMNS,
    KANBAN_ROOT,
    Card,
    ensure_initialized,
    iter_cards,
)

PRIORITY_ORDER = {"high": 0, "med": 1, "low": 2}
DONE_CAP = 50
SCRIPT_DIR = Path(__file__).parent
MOVE_SCRIPT = SCRIPT_DIR / "kanban-move.py"
NEW_SCRIPT = SCRIPT_DIR / "kanban-new.py"
SET_SCRIPT = SCRIPT_DIR / "kanban-set.py"
RM_SCRIPT = SCRIPT_DIR / "kanban-rm.py"


def card_sort_key(c: Card) -> tuple:
    pr = PRIORITY_ORDER.get(c.frontmatter.get("priority", "med"), 1)
    due = c.frontmatter.get("due") or "9999-99-99"
    return (pr, str(due), c.id)


def completion_sort_key(c: Card) -> str:
    ts = c.frontmatter.get("completed_at")
    if ts:
        return str(ts)
    try:
        return dt.datetime.fromtimestamp(c.path.stat().st_mtime).isoformat()
    except OSError:
        return c.id


def card_to_dict(c: Card) -> dict:
    fm = c.frontmatter
    created = fm.get("created")
    if isinstance(created, (dt.datetime, dt.date)):
        created = created.isoformat()
    completed_at = fm.get("completed_at")
    if isinstance(completed_at, (dt.datetime, dt.date)):
        completed_at = completed_at.isoformat()
    due = fm.get("due")
    if isinstance(due, (dt.datetime, dt.date)):
        due = due.isoformat()
    tags = fm.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]
    return {
        "id": c.id,
        "slug": c.slug,
        "title": c.title,
        "project": c.project,
        "priority": fm.get("priority"),
        "tags": [str(t) for t in tags],
        "due": str(due) if due else None,
        "type": fm.get("type"),
        "epic": fm.get("epic"),
        "blocked_by": fm.get("blocked_by"),
        "completed_at": str(completed_at) if completed_at else None,
        "created": str(created) if created else None,
        "body_md": c.body,
    }


def build_state() -> dict:
    cards_by_col: dict[str, list[Card]] = {col: [] for col in COLUMNS}
    projects: set[str] = set()
    mtime_max = 0.0
    total = 0

    for card in iter_cards(COLUMNS):
        cards_by_col[card.column].append(card)
        if card.project:
            projects.add(card.project)
        try:
            mtime_max = max(mtime_max, card.path.stat().st_mtime)
        except OSError:
            pass
        total += 1

    cards_by_col["Backlog"].sort(key=card_sort_key)
    cards_by_col["InProgress"].sort(key=card_sort_key)
    cards_by_col["Blocked"].sort(key=card_sort_key)
    cards_by_col["Done"].sort(key=completion_sort_key, reverse=True)
    cards_by_col["Done"] = cards_by_col["Done"][:DONE_CAP]

    cards_json = {
        col: [card_to_dict(c) for c in cards_by_col[col]] for col in COLUMNS
    }
    version = hashlib.sha1(
        f"{mtime_max:.6f}:{total}".encode()
    ).hexdigest()[:12]

    return {
        "version": version,
        "columns": COLUMNS,
        "cards": cards_json,
        "projects": sorted(projects),
    }


def _run_script(script: Path, args: list[str], timeout: int = 15) -> tuple[bool, str, str]:
    cmd = [str(script), *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "", f"{script.name} timed out"
    except FileNotFoundError:
        return False, "", f"{script.name} not found at {script}"
    return r.returncode == 0, r.stdout.strip(), r.stderr.strip()


def run_move(card_id: str, target: str, by: str | None) -> tuple[bool, str, str]:
    args = [card_id, target]
    if by:
        args += ["--by", by]
    return _run_script(MOVE_SCRIPT, args)


def run_new(title: str, project: str, card_type: str, priority: str | None,
            tags: str | None, due: str | None) -> tuple[bool, str, str]:
    args = [title, "--project", project, "--type", card_type]
    if priority and priority != "none":
        args += ["--priority", priority]
    if tags:
        args += ["--tags", tags]
    if due:
        args += ["--due", due]
    return _run_script(NEW_SCRIPT, args)


def run_set(card_id: str, fields: dict) -> tuple[bool, str, str]:
    args = [card_id]
    for k in ("title", "priority", "tags", "due", "epic", "type", "project"):
        v = fields.get(k)
        if v is None or v == "":
            continue
        args += [f"--{k}", str(v)]
    if len(args) == 1:
        return False, "", "no fields to update"
    return _run_script(SET_SCRIPT, args)


def run_rm(card_id: str, hard: bool = False) -> tuple[bool, str, str]:
    args = [card_id]
    if hard:
        args.append("--hard")
    return _run_script(RM_SCRIPT, args)


class Handler(BaseHTTPRequestHandler):
    server_version = "kanban-serve/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(
            f"[{dt.datetime.now().strftime('%H:%M:%S')}] {fmt % args}\n"
        )

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/" or self.path == "/index.html":
            self._send_html(INDEX_HTML)
            return
        if self.path == "/api/state":
            try:
                state = build_state()
            except Exception as e:
                self._send_json(500, {"error": str(e)})
                return
            self._send_json(200, state)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid json"})
            return None

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/move":
            return self._handle_move()
        if self.path == "/api/new":
            return self._handle_new()
        if self.path == "/api/set":
            return self._handle_set()
        if self.path == "/api/rm":
            return self._handle_rm()
        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def _handle_move(self) -> None:
        data = self._read_json()
        if data is None:
            return
        card_id = str(data.get("id") or "").strip()
        target = str(data.get("to") or "").strip()
        by = data.get("by")
        if not card_id or not target:
            self._send_json(400, {"ok": False, "error": "id and to required"})
            return

        from_col = None
        try:
            for c in iter_cards(COLUMNS):
                if c.id == card_id:
                    from_col = c.column
                    break
        except Exception:
            pass

        ok, stdout, stderr = run_move(card_id, target, by if isinstance(by, str) else None)
        if not ok:
            self._send_json(400, {"ok": False, "error": stderr or stdout or "move failed"})
            return
        self._send_json(200, {
            "ok": True, "id": card_id, "from": from_col, "to": target, "stdout": stdout,
        })

    def _handle_new(self) -> None:
        data = self._read_json()
        if data is None:
            return
        title = str(data.get("title") or "").strip()
        project = str(data.get("project") or "").strip()
        if not title or not project:
            self._send_json(400, {"ok": False, "error": "title and project required"})
            return
        priority = data.get("priority") or None
        tags = data.get("tags") or None
        due = data.get("due") or None
        card_type = str(data.get("type") or "task")
        if card_type not in {"task", "epic"}:
            self._send_json(400, {"ok": False, "error": "type must be task or epic"})
            return
        ok, stdout, stderr = run_new(title, project, card_type,
                                     str(priority) if priority else None,
                                     str(tags) if tags else None,
                                     str(due) if due else None)
        if not ok:
            self._send_json(400, {"ok": False, "error": stderr or stdout or "create failed"})
            return
        self._send_json(200, {"ok": True, "stdout": stdout})

    def _handle_set(self) -> None:
        data = self._read_json()
        if data is None:
            return
        card_id = str(data.get("id") or "").strip()
        if not card_id:
            self._send_json(400, {"ok": False, "error": "id required"})
            return
        fields = {k: data.get(k) for k in ("title", "priority", "tags", "due", "epic", "project")}
        ok, stdout, stderr = run_set(card_id, fields)
        if not ok:
            self._send_json(400, {"ok": False, "error": stderr or stdout or "set failed"})
            return
        self._send_json(200, {"ok": True, "id": card_id, "stdout": stdout})

    def _handle_rm(self) -> None:
        data = self._read_json()
        if data is None:
            return
        card_id = str(data.get("id") or "").strip()
        hard = bool(data.get("hard"))
        if not card_id:
            self._send_json(400, {"ok": False, "error": "id required"})
            return
        ok, stdout, stderr = run_rm(card_id, hard=hard)
        if not ok:
            self._send_json(400, {"ok": False, "error": stderr or stdout or "remove failed"})
            return
        self._send_json(200, {"ok": True, "id": card_id, "stdout": stdout})


INDEX_HTML = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Kanban</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  :root {
    --bar: #0079bf;
    --bar-dark: #026aa7;
    --board-bg: #f4f5f7;
    --col-bg: #ebecf0;
    --card-bg: #ffffff;
    --card-shadow: 0 1px 0 rgba(9,30,66,.25);
    --text: #172b4d;
    --muted: #5e6c84;
    --high: #eb5a46;
    --med: #f2d600;
    --low: #c1c7d0;
    --danger: #eb5a46;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; height: 100%; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue",
      Arial, "Noto Sans KR", sans-serif;
    background: var(--board-bg);
    color: var(--text);
    font-size: 14px;
  }
  header {
    background: var(--bar);
    color: #fff;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    gap: 14px;
    box-shadow: 0 1px 0 rgba(0,0,0,0.1);
  }
  header h1 {
    font-size: 16px;
    margin: 0;
    font-weight: 600;
    letter-spacing: 0.2px;
  }
  header .spacer { flex: 1; }
  header select, header input[type=search] {
    background: rgba(255,255,255,0.2);
    color: #fff;
    border: 1px solid rgba(255,255,255,0.3);
    padding: 4px 8px;
    border-radius: 3px;
    font-size: 13px;
  }
  header input[type=search]::placeholder { color: rgba(255,255,255,0.7); }
  header select option { color: #172b4d; }
  header button.new-btn {
    background: rgba(255,255,255,0.95);
    color: #0079bf;
    border: 0;
    padding: 5px 12px;
    border-radius: 3px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
  }
  header button.new-btn:hover { background: #fff; }
  .conn-dot {
    width: 9px; height: 9px; border-radius: 50%;
    background: #5aac44;
    box-shadow: 0 0 0 2px rgba(255,255,255,0.3);
  }
  .conn-dot.err { background: #eb5a46; }
  .board {
    padding: 12px;
    display: grid;
    grid-template-columns: repeat(4, minmax(240px, 1fr));
    gap: 12px;
    height: calc(100vh - 48px);
    overflow-x: auto;
  }
  .col {
    background: var(--col-bg);
    border-radius: 4px;
    display: flex;
    flex-direction: column;
    min-width: 240px;
    max-height: 100%;
  }
  .col-header {
    padding: 10px 12px 6px;
    font-weight: 600;
    font-size: 13px;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .col-count {
    color: var(--muted);
    font-weight: 500;
    font-size: 12px;
  }
  .col-body {
    padding: 4px 8px 8px;
    overflow-y: auto;
    flex: 1;
    min-height: 60px;
  }
  .col-body.drop-target {
    background: rgba(0, 121, 191, 0.08);
    box-shadow: inset 0 0 0 2px rgba(0, 121, 191, 0.4);
    border-radius: 4px;
  }
  .card {
    background: var(--card-bg);
    border-radius: 3px;
    padding: 8px 10px;
    margin-bottom: 6px;
    box-shadow: var(--card-shadow);
    cursor: grab;
    user-select: none;
    border-left: 3px solid transparent;
  }
  .card:hover { background: #fafbfc; }
  .card.dragging { opacity: 0.5; cursor: grabbing; }
  .card.priority-high { border-left-color: var(--high); }
  .card.priority-med  { border-left-color: var(--med); }
  .card.priority-low  { border-left-color: var(--low); }
  .card-title {
    font-weight: 500;
    line-height: 1.35;
    margin-bottom: 4px;
    word-break: break-word;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 4px;
  }
  .chip {
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 3px;
    background: #dfe1e6;
    color: var(--text);
    line-height: 1.3;
  }
  .chip.project {
    color: #fff;
    font-weight: 500;
  }
  .meta {
    font-size: 11px;
    color: var(--muted);
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .meta .due.past { color: var(--danger); font-weight: 600; }
  .meta .blocked { color: var(--danger); }

  /* Modal */
  .modal-back {
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.45);
    display: none;
    align-items: flex-start;
    justify-content: center;
    padding: 40px 16px;
    z-index: 100;
    overflow-y: auto;
  }
  .modal-back.open { display: flex; }
  .modal {
    background: #fff;
    border-radius: 6px;
    padding: 20px 24px 24px;
    max-width: 720px;
    width: 100%;
    box-shadow: 0 8px 32px rgba(9,30,66,0.3);
  }
  .modal h2 { margin: 0 0 8px; font-size: 18px; }
  .modal .meta-table {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 4px 12px;
    font-size: 12px;
    color: var(--muted);
    margin: 12px 0 16px;
  }
  .modal .meta-table dt { font-weight: 600; }
  .modal .body {
    border-top: 1px solid #dfe1e6;
    padding-top: 14px;
    line-height: 1.55;
    word-wrap: break-word;
  }
  .modal .body h1, .modal .body h2, .modal .body h3 {
    margin: 12px 0 6px;
  }
  .modal .body code {
    background: #f4f5f7;
    padding: 1px 4px;
    border-radius: 2px;
    font-size: 13px;
  }
  .modal .body pre {
    background: #f4f5f7;
    padding: 10px;
    border-radius: 3px;
    overflow-x: auto;
  }
  .modal .body pre code { background: transparent; padding: 0; }
  .modal .close {
    float: right;
    background: transparent;
    border: 0;
    font-size: 22px;
    color: var(--muted);
    cursor: pointer;
    line-height: 1;
  }
  .modal .empty-body { color: var(--muted); font-style: italic; }
  .modal .actions {
    display: flex;
    gap: 8px;
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid #dfe1e6;
  }
  .modal .actions button {
    border: 0;
    padding: 6px 12px;
    border-radius: 3px;
    font-size: 13px;
    cursor: pointer;
    font-weight: 500;
  }
  .modal .actions .edit { background: #0079bf; color: #fff; }
  .modal .actions .edit:hover { background: #026aa7; }
  .modal .actions .delete { background: transparent; color: var(--danger); margin-left: auto; }
  .modal .actions .delete:hover { background: rgba(235,90,70,0.1); }
  .modal .actions .save { background: #5aac44; color: #fff; }
  .modal .actions .save:hover { background: #4f9c3a; }
  .modal .actions .cancel { background: #dfe1e6; color: var(--text); }
  .form-grid {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 8px 12px;
    align-items: center;
    margin: 12px 0 8px;
  }
  .form-grid label {
    font-size: 12px;
    color: var(--muted);
    font-weight: 600;
  }
  .form-grid input, .form-grid select {
    width: 100%;
    padding: 6px 8px;
    border: 1px solid #dfe1e6;
    border-radius: 3px;
    font-size: 13px;
    font-family: inherit;
    box-sizing: border-box;
  }
  .form-grid input:focus, .form-grid select:focus {
    outline: 0;
    border-color: #0079bf;
  }
  .form-grid input.req-empty { border-color: var(--danger); }
  .modal .hint { font-size: 11px; color: var(--muted); margin-top: -4px; }

  /* Toast */
  .toast {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: #172b4d;
    color: #fff;
    padding: 10px 16px;
    border-radius: 4px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    font-size: 13px;
    max-width: 480px;
    z-index: 200;
    opacity: 0;
    transition: opacity 0.2s;
    pointer-events: none;
  }
  .toast.show { opacity: 1; }
  .toast.err { background: var(--danger); }
</style>
</head>
<body>
<header>
  <h1>Kanban</h1>
  <span id="total-count" class="col-count" style="color:rgba(255,255,255,0.85)"></span>
  <input id="search" type="search" placeholder="🔍 Search title/tag/id…" />
  <div class="spacer"></div>
  <label style="font-size:12px;opacity:.85">Project</label>
  <select id="project-filter"><option value="">All</option></select>
  <button class="new-btn" id="new-btn">+ New</button>
  <span id="conn" class="conn-dot" title="connected"></span>
</header>
<main class="board" id="board"></main>

<div class="modal-back" id="modal-back">
  <div class="modal" id="modal"></div>
</div>

<div class="toast" id="toast"></div>

<script>
const COLUMNS = ["Backlog", "InProgress", "Done", "Blocked"];
const COLUMN_LABELS = {
  Backlog: "Backlog",
  InProgress: "In Progress",
  Done: "Done",
  Blocked: "Blocked",
};
const PRIORITY_LABEL = { high: "High", med: "Med", low: "Low" };

const ui = {
  board: document.getElementById("board"),
  totalCount: document.getElementById("total-count"),
  projectFilter: document.getElementById("project-filter"),
  search: document.getElementById("search"),
  newBtn: document.getElementById("new-btn"),
  conn: document.getElementById("conn"),
  modalBack: document.getElementById("modal-back"),
  modal: document.getElementById("modal"),
  toast: document.getElementById("toast"),
};

const state = {
  lastVersion: null,
  data: null,
  projectFilter: "",
  search: "",
  dragging: false,
  modalOpen: false,
  movePending: null,
  pollMs: 3000,
  errBackoffMs: 10000,
};

// --- helpers ---
function projectColor(name) {
  // deterministic HSL hash
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return `hsl(${h % 360}, 50%, 45%)`;
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}
function todayStr() {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}
function showToast(msg, isErr) {
  ui.toast.textContent = msg;
  ui.toast.className = "toast show" + (isErr ? " err" : "");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => {
    ui.toast.classList.remove("show");
  }, 4000);
}

// --- rendering ---
function renderCard(card) {
  const el = document.createElement("div");
  el.className = "card";
  if (card.priority) el.classList.add("priority-" + card.priority);
  el.draggable = true;
  el.dataset.id = card.id;

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = card.title;
  el.appendChild(title);

  const chips = document.createElement("div");
  chips.className = "chips";
  if (card.project) {
    const p = document.createElement("span");
    p.className = "chip project";
    p.style.background = projectColor(card.project);
    p.textContent = card.project;
    chips.appendChild(p);
  }
  (card.tags || []).forEach(t => {
    const c = document.createElement("span");
    c.className = "chip";
    c.textContent = t;
    chips.appendChild(c);
  });
  if (chips.childNodes.length) el.appendChild(chips);

  const meta = document.createElement("div");
  meta.className = "meta";
  if (card.due) {
    const d = document.createElement("span");
    d.className = "due" + (card.due < todayStr() && !card.completed_at ? " past" : "");
    d.textContent = "📅 " + card.due;
    meta.appendChild(d);
  }
  if (card.blocked_by) {
    const b = document.createElement("span");
    b.className = "blocked";
    b.textContent = "⛔ " + card.blocked_by;
    meta.appendChild(b);
  }
  if (card.type === "epic") {
    const t = document.createElement("span");
    t.textContent = "🪐 epic";
    meta.appendChild(t);
  }
  if (card.epic) {
    const e = document.createElement("span");
    e.textContent = "epic→" + card.epic;
    meta.appendChild(e);
  }
  if (card.completed_at) {
    const c = document.createElement("span");
    c.textContent = "✓ " + String(card.completed_at).slice(0, 10);
    meta.appendChild(c);
  }
  if (meta.childNodes.length) el.appendChild(meta);

  // drag handlers
  el.addEventListener("dragstart", (e) => {
    state.dragging = true;
    el.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", card.id);
  });
  el.addEventListener("dragend", () => {
    state.dragging = false;
    el.classList.remove("dragging");
    document.querySelectorAll(".col-body.drop-target")
      .forEach(n => n.classList.remove("drop-target"));
  });
  el.addEventListener("click", (e) => {
    if (state.dragging) return;
    openModal(card);
  });
  return el;
}

function renderBoard() {
  if (!state.data) return;
  const data = state.data;
  ui.board.innerHTML = "";
  let total = 0;
  for (const col of COLUMNS) {
    let cards = data.cards[col] || [];
    if (state.projectFilter) {
      cards = cards.filter(c => c.project === state.projectFilter);
    }
    if (state.search) {
      const q = state.search.toLowerCase();
      cards = cards.filter(c => {
        const hay = [
          c.title, c.id, c.project,
          ...(c.tags || []),
          c.body_md || "",
        ].join(" ").toLowerCase();
        return hay.includes(q);
      });
    }
    total += cards.length;

    const section = document.createElement("section");
    section.className = "col";
    section.dataset.column = col;

    const header = document.createElement("div");
    header.className = "col-header";
    header.innerHTML = `<span>${COLUMN_LABELS[col]}</span>` +
      `<span class="col-count">${cards.length}</span>`;
    section.appendChild(header);

    const body = document.createElement("div");
    body.className = "col-body";
    body.dataset.column = col;
    body.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      body.classList.add("drop-target");
    });
    body.addEventListener("dragleave", () => body.classList.remove("drop-target"));
    body.addEventListener("drop", (e) => {
      e.preventDefault();
      body.classList.remove("drop-target");
      const id = e.dataTransfer.getData("text/plain");
      if (id) handleDrop(id, col);
    });

    for (const card of cards) body.appendChild(renderCard(card));
    section.appendChild(body);
    ui.board.appendChild(section);
  }
  ui.totalCount.textContent = total + " cards";

  // refresh project filter options without losing current selection
  const seen = new Set(["", ...(data.projects || [])]);
  const cur = ui.projectFilter.value;
  const want = ["", ...(data.projects || [])];
  const have = Array.from(ui.projectFilter.options).map(o => o.value);
  if (JSON.stringify(want) !== JSON.stringify(have)) {
    ui.projectFilter.innerHTML = "";
    for (const p of want) {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p === "" ? "All" : p;
      ui.projectFilter.appendChild(opt);
    }
    if (seen.has(cur)) ui.projectFilter.value = cur;
  }
}

// --- modal ---
function closeModal() {
  state.modalOpen = false;
  ui.modalBack.classList.remove("open");
  ui.modal.innerHTML = "";
}
function showModal() {
  state.modalOpen = true;
  ui.modalBack.classList.add("open");
}
ui.modalBack.addEventListener("click", (e) => {
  if (e.target === ui.modalBack) closeModal();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && state.modalOpen) closeModal();
});

function renderViewMode(card) {
  const rows = [
    ["id", card.id],
    ["project", card.project],
    ["priority", card.priority ? PRIORITY_LABEL[card.priority] || card.priority : null],
    ["tags", (card.tags || []).join(", ") || null],
    ["due", card.due],
    ["created", card.created],
    ["completed_at", card.completed_at],
    ["type", card.type],
    ["epic", card.epic],
    ["blocked_by", card.blocked_by],
  ].filter(([, v]) => v);
  const metaHtml = rows.map(([k, v]) =>
    `<dt>${k}</dt><dd>${escapeHtml(v)}</dd>`
  ).join("");
  const bodyHtml = (card.body_md && card.body_md.trim())
    ? marked.parse(card.body_md, { mangle: false, headerIds: false, breaks: false })
    : '<p class="empty-body">(no description)</p>';

  ui.modal.innerHTML = `
    <button class="close" aria-label="Close">&times;</button>
    <h2>${escapeHtml(card.title)}</h2>
    <dl class="meta-table">${metaHtml}</dl>
    <div class="body">${bodyHtml}</div>
    <div class="actions">
      <button class="edit">Edit</button>
      <button class="delete">Delete (Archive)</button>
    </div>
  `;
  ui.modal.querySelector(".close").addEventListener("click", closeModal);
  ui.modal.querySelector(".edit").addEventListener("click", () => renderEditMode(card));
  ui.modal.querySelector(".delete").addEventListener("click", () => handleDelete(card));
}

function renderEditMode(card) {
  ui.modal.innerHTML = `
    <button class="close" aria-label="Close">&times;</button>
    <h2>Edit · <span style="font-weight:400;color:var(--muted);font-size:13px">${escapeHtml(card.id)}</span></h2>
    <div class="form-grid">
      <label>Title</label><input id="f-title" type="text" value="${escapeHtml(card.title)}" />
      <label>Project</label><input id="f-project" type="text" value="${escapeHtml(card.project || "")}" />
      <label>Priority</label>
      <select id="f-priority">
        <option value="">—</option>
        <option value="high"${card.priority === "high" ? " selected" : ""}>High</option>
        <option value="med"${card.priority === "med" ? " selected" : ""}>Med</option>
        <option value="low"${card.priority === "low" ? " selected" : ""}>Low</option>
      </select>
      <label>Tags</label><input id="f-tags" type="text" value="${escapeHtml((card.tags || []).join(", "))}" placeholder="comma, separated" />
      <label>Due</label><input id="f-due" type="date" value="${escapeHtml(card.due || "")}" />
    </div>
    <p class="hint">본문(body)은 파일 직접 수정 — 3초 안에 자동 반영됨.</p>
    <div class="actions">
      <button class="save">Save</button>
      <button class="cancel">Cancel</button>
    </div>
  `;
  ui.modal.querySelector(".close").addEventListener("click", closeModal);
  ui.modal.querySelector(".cancel").addEventListener("click", () => renderViewMode(card));
  ui.modal.querySelector(".save").addEventListener("click", () => handleSave(card));
}

function renderNewMode() {
  const projectsList = (state.data?.projects || []).map(p =>
    `<option value="${escapeHtml(p)}">`
  ).join("");
  ui.modal.innerHTML = `
    <button class="close" aria-label="Close">&times;</button>
    <h2>New card</h2>
    <div class="form-grid">
      <label>Title *</label><input id="f-title" type="text" placeholder="What needs doing?" />
      <label>Project *</label>
      <input id="f-project" type="text" list="proj-list" placeholder="project name" />
      <datalist id="proj-list">${projectsList}</datalist>
      <label>Type</label>
      <select id="f-type">
        <option value="task">Task</option>
        <option value="epic">Epic</option>
      </select>
      <label>Priority</label>
      <select id="f-priority">
        <option value="">—</option>
        <option value="high">High</option>
        <option value="med">Med</option>
        <option value="low">Low</option>
      </select>
      <label>Tags</label><input id="f-tags" type="text" placeholder="comma, separated" />
      <label>Due</label><input id="f-due" type="date" />
    </div>
    <p class="hint">Backlog에 생성됩니다. 본문은 파일로 직접 추가하세요.</p>
    <div class="actions">
      <button class="save">Create</button>
      <button class="cancel">Cancel</button>
    </div>
  `;
  ui.modal.querySelector(".close").addEventListener("click", closeModal);
  ui.modal.querySelector(".cancel").addEventListener("click", closeModal);
  ui.modal.querySelector(".save").addEventListener("click", handleCreate);
  setTimeout(() => ui.modal.querySelector("#f-title")?.focus(), 0);
}

function openModal(card) { renderViewMode(card); showModal(); }
function openNewModal() { renderNewMode(); showModal(); }

async function handleSave(originalCard) {
  const title = ui.modal.querySelector("#f-title").value.trim();
  const project = ui.modal.querySelector("#f-project").value.trim();
  const priority = ui.modal.querySelector("#f-priority").value;
  const type = ui.modal.querySelector("#f-type").value || "task";
  const tags = ui.modal.querySelector("#f-tags").value.trim();
  const due = ui.modal.querySelector("#f-due").value;

  if (!title) {
    showToast("Title required", true);
    return;
  }
  // Build payload of only-changed fields.
  const payload = { id: originalCard.id };
  if (title !== originalCard.title) payload.title = title;
  if (project !== (originalCard.project || "")) payload.project = project;
  if (priority !== (originalCard.priority || "")) {
    payload.priority = priority || "none";
  }
  const origTags = (originalCard.tags || []).join(", ");
  if (tags !== origTags) {
    payload.tags = tags || "none";
  }
  if (due !== (originalCard.due || "")) {
    payload.due = due || "none";
  }
  if (Object.keys(payload).length === 1) {
    closeModal();
    return;
  }

  try {
    const r = await fetch("/api/set", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const j = await r.json();
    if (!r.ok || !j.ok) throw new Error(j.error || `HTTP ${r.status}`);
    showToast("Saved");
    closeModal();
    await fetchState(true);
  } catch (e) {
    showToast("Save failed: " + e.message, true);
  }
}

async function handleDelete(card) {
  if (!confirm(`Archive "${card.title}"? (move to Archive/ folder)`)) return;
  try {
    const r = await fetch("/api/rm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: card.id }),
    });
    const j = await r.json();
    if (!r.ok || !j.ok) throw new Error(j.error || `HTTP ${r.status}`);
    showToast("Archived");
    closeModal();
    await fetchState(true);
  } catch (e) {
    showToast("Delete failed: " + e.message, true);
  }
}

async function handleCreate() {
  const title = ui.modal.querySelector("#f-title").value.trim();
  const project = ui.modal.querySelector("#f-project").value.trim();
  const priority = ui.modal.querySelector("#f-priority").value;
  const tags = ui.modal.querySelector("#f-tags").value.trim();
  const due = ui.modal.querySelector("#f-due").value;

  if (!title || !project) {
    if (!title) ui.modal.querySelector("#f-title").classList.add("req-empty");
    if (!project) ui.modal.querySelector("#f-project").classList.add("req-empty");
    showToast("Title and project required", true);
    return;
  }

  try {
    const r = await fetch("/api/new", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, project, type, priority, tags, due }),
    });
    const j = await r.json();
    if (!r.ok || !j.ok) throw new Error(j.error || `HTTP ${r.status}`);
    showToast("Created");
    closeModal();
    await fetchState(true);
  } catch (e) {
    showToast("Create failed: " + e.message, true);
  }
}

// --- drag-drop wiring ---
async function handleDrop(id, targetCol) {
  // find current location of card
  let card = null, fromCol = null;
  for (const col of COLUMNS) {
    const found = (state.data.cards[col] || []).find(c => c.id === id);
    if (found) { card = found; fromCol = col; break; }
  }
  if (!card) return;
  if (fromCol === targetCol) return;
  if (state.movePending === id) return;

  // optimistic UI: move card in local state and re-render
  state.data.cards[fromCol] = state.data.cards[fromCol].filter(c => c.id !== id);
  if (targetCol === "Done") {
    card.completed_at = new Date().toISOString();
    card.blocked_by = null;
  } else if (targetCol !== "Blocked") {
    card.blocked_by = null;
    card.completed_at = null;
  }
  state.data.cards[targetCol] = [card, ...(state.data.cards[targetCol] || [])];
  renderBoard();

  state.movePending = id;
  try {
    const r = await fetch("/api/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, to: targetCol.toLowerCase() }),
    });
    const j = await r.json();
    if (!r.ok || !j.ok) {
      showToast("Move failed: " + (j.error || r.status), true);
      // snap back via authoritative fetch
      await fetchState(true);
    } else {
      // force a refresh to sync sort order, completed_at, etc.
      await fetchState(true);
    }
  } catch (err) {
    showToast("Move failed: " + err.message, true);
    await fetchState(true);
  } finally {
    state.movePending = null;
  }
}

// --- polling ---
async function fetchState(force) {
  if (!force && (state.dragging || state.modalOpen || state.movePending)) return;
  try {
    const r = await fetch("/api/state");
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    ui.conn.classList.remove("err");
    ui.conn.title = "connected";
    if (data.version !== state.lastVersion) {
      state.lastVersion = data.version;
      state.data = data;
      renderBoard();
    }
    return true;
  } catch (e) {
    ui.conn.classList.add("err");
    ui.conn.title = "disconnected: " + e.message;
    return false;
  }
}

ui.projectFilter.addEventListener("change", () => {
  state.projectFilter = ui.projectFilter.value;
  renderBoard();
});
ui.search.addEventListener("input", () => {
  state.search = ui.search.value.trim();
  renderBoard();
});
ui.newBtn.addEventListener("click", openNewModal);
document.addEventListener("keydown", (e) => {
  // "/" focuses search (when not already in an input)
  if (e.key === "/" && !["INPUT","TEXTAREA","SELECT"].includes(document.activeElement?.tagName)) {
    e.preventDefault();
    ui.search.focus();
  }
});

// initial fetch + polling loop
async function loop() {
  while (true) {
    const ok = await fetchState(false);
    await new Promise(res => setTimeout(res, ok ? state.pollMs : state.errBackoffMs));
  }
}
fetchState(true).then(loop);
</script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live web viewer for ~/wiki/Kanban/.")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--no-browser", action="store_true",
                   help="Do not auto-open the browser.")
    p.add_argument("--allow-lan", action="store_true",
                   help="Allow binding to non-loopback (e.g. 0.0.0.0).")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ensure_initialized()

    if not MOVE_SCRIPT.exists():
        print(f"error: {MOVE_SCRIPT} not found", file=sys.stderr)
        sys.exit(2)

    is_loopback = args.host in ("127.0.0.1", "localhost", "::1")
    if not is_loopback and not args.allow_lan:
        print(
            f"error: refusing to bind {args.host} (non-loopback). "
            f"Pass --allow-lan to override.",
            file=sys.stderr,
        )
        sys.exit(2)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"kanban-serve listening on {url}")
    print(f"  root: {KANBAN_ROOT}")
    print("  press Ctrl-C to stop")

    if not args.no_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
