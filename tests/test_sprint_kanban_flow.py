from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, relative_path: str):
    path = ROOT / relative_path
    script_dir = str(path.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def init_kanban_root(tmp_path: Path) -> Path:
    root = tmp_path / "wiki" / "Kanban"
    for column in ("Backlog", "InProgress", "Blocked", "Done", "Archive"):
        (root / column).mkdir(parents=True, exist_ok=True)
    (root / "BOARD.md").write_text("# Board\n", encoding="utf-8")
    return root


def write_card(path: Path, frontmatter: dict, body: str = "## 배경\n\n테스트 카드\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).rstrip()
    path.write_text(f"---\n{fm}\n---\n\n{body}", encoding="utf-8")


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    fm_text = text.split("---", 2)[1]
    return yaml.safe_load(fm_text) or {}


def write_planning(path: Path, gates: str, summary: str = "스프린트 목표") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
project: demo
sprint: 0.2.0
---

## 한 줄 요약

{summary}

## Core Gates

{gates}
""",
        encoding="utf-8",
    )


def write_progress(path: Path, checked: bool = False) -> None:
    mark = "x" if checked else " "
    memo = "정상 검증이 충분한 설명으로 완료되어 회귀 기준까지 확인함 2026-05-10" if checked else "<검증 메모, 날짜>"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""---
created: 2026-05-10
updated: 2026-05-10
type: project_spec
status: growing
project: demo
sprint: 0.2.0
---

# demo — 0.2.0 Readiness Gates (DRAFT)

## 게이트

### G1. 로그인 실패 메시지 수정
- [{mark}] **happy** — {memo}
- [{mark}] **isolation_failure** — {memo}
- [{mark}] **expected_reaction** — {memo}

## 검증 로그

| 날짜 | 게이트 | 결과 | 메모 |
|---|---|---|---|
""",
        encoding="utf-8",
    )


def run_cli(home: Path, relative_path: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, str(ROOT / relative_path), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"{relative_path} {' '.join(args)} failed with {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def parse_added_id(stdout: str) -> str:
    m = re.search(r"^added: \[([\w\d-]+)\]", stdout, re.M)
    assert m, stdout
    return m.group(1)


def parse_published_gate_id(stdout: str, gate: str) -> str:
    m = re.search(rf"^\s*✓ {re.escape(gate)} 발행: \[([\w\d-]+)\]", stdout, re.M)
    assert m, stdout
    return m.group(1)


def test_kanban_new_requires_llm_decided_type_and_records_epic_breakdown_tag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kanban_new = load_script(
        "kanban_new_under_test",
        "kangnam-dev/skills/kanban/scripts/kanban-new.py",
    )
    kanban_core = sys.modules["_kanban"]
    kanban_root = init_kanban_root(tmp_path)
    monkeypatch.setattr(kanban_new, "KANBAN_ROOT", kanban_root)
    monkeypatch.setattr(kanban_core, "KANBAN_ROOT", kanban_root)
    monkeypatch.setattr(kanban_new, "regenerate_board", lambda: None)

    monkeypatch.setattr(sys, "argv", ["kanban-new.py", "결제 구조 개선"])
    with pytest.raises(SystemExit) as missing_type:
        kanban_new.parse_args()
    assert missing_type.value.code == 2

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kanban-new.py",
            "결제 구조 개선",
            "--project",
            "demo",
            "--type",
            "epic",
            "--note",
            "언젠가 전체 결제 흐름을 정리하고 싶음",
        ],
    )
    kanban_new.main()
    epic_path = next((kanban_root / "Backlog").glob("*.md"))
    epic_fm = read_frontmatter(epic_path)
    assert epic_fm["type"] == "epic"
    assert "needs-breakdown" in epic_fm["tags"]
    assert "언젠가 전체 결제 흐름" in epic_path.read_text(encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kanban-new.py",
            "로그인 실패 메시지 수정",
            "--project",
            "demo",
            "--type",
            "task",
        ],
    )
    kanban_new.main()
    cards = sorted((kanban_root / "Backlog").glob("*.md"))
    task_path = [p for p in cards if p != epic_path][0]
    task_fm = read_frontmatter(task_path)
    assert task_fm.get("type") is None
    assert "needs-breakdown" not in (task_fm.get("tags") or [])


def test_sprint_planning_intake_lists_task_and_epic_with_breakdown_guidance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sprint_planning = load_script(
        "sprint_planning_under_test",
        "kangnam-dev/scripts/sprint/sprint-planning.py",
    )
    wiki_root = tmp_path / "wiki"
    kanban_root = init_kanban_root(tmp_path)
    monkeypatch.setattr(sprint_planning, "WIKI_ROOT", wiki_root)

    write_card(
        kanban_root / "Backlog" / "login-message.md",
        {
            "id": "260101-0001",
            "created": "2026-01-01T00:01:00+09:00",
            "title": "로그인 실패 메시지 수정",
            "project": "demo",
        },
    )
    write_card(
        kanban_root / "Backlog" / "payment-structure.md",
        {
            "id": "260101-0002",
            "created": "2026-01-01T00:02:00+09:00",
            "title": "결제 구조 개선",
            "project": "demo",
            "type": "epic",
            "tags": ["needs-breakdown"],
        },
    )

    intake = sprint_planning.build_sprint_intake("demo", "0.2.0", prev_sprint=None)

    assert "[260101-0001] 로그인 실패 메시지 수정" in intake
    assert "type: task" in intake
    assert "[260101-0002] 결제 구조 개선" in intake
    assert "type: epic" in intake
    assert "reason: needs-breakdown-epic" in intake
    assert "`source_epic`" in intake


def test_publish_rejects_mapping_epic_as_direct_gate_card(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    publish = load_script(
        "sprint_publish_reject_under_test",
        "kangnam-dev/scripts/sprint/sprint-publish-cards.py",
    )
    kanban_root = init_kanban_root(tmp_path)
    planning_dir = tmp_path / "wiki" / "Projects" / "demo" / "Sprints" / "0.2.0"
    planning_dir.mkdir(parents=True)
    (planning_dir / "planning.md").write_text(
        """---
project: demo
sprint: 0.2.0
---

## 한 줄 요약

결제 정리

## Core Gates

### G1. 결제 실패 메시지 통일
- **domain**: `backend`
- **card**: `260101-0001`
- **source_epic**: `none`
- **happy** — ok
  - 검증: `manual`
- **isolation_failure** — fail
  - 검증: `manual`
- **expected_reaction** — react
  - 검증: `manual`
""",
        encoding="utf-8",
    )
    write_card(
        kanban_root / "Backlog" / "payment-epic.md",
        {
            "id": "260101-0001",
            "created": "2026-01-01T00:01:00+09:00",
            "title": "결제 구조 개선",
            "project": "demo",
            "type": "epic",
        },
    )

    monkeypatch.setattr(publish, "KANBAN_ROOT", kanban_root)
    monkeypatch.setattr(publish, "project_dir", lambda project: tmp_path / "wiki" / "Projects" / project)
    monkeypatch.setattr(publish, "normalize_version", lambda project, version: version)
    monkeypatch.setattr(publish, "sprint_dir", lambda project, version: planning_dir)
    monkeypatch.setattr(publish, "run_kanban_new", lambda *args: pytest.fail("must not create card"))
    monkeypatch.setattr(publish, "run_kanban_set", lambda *args: pytest.fail("must not mutate epic"))
    monkeypatch.setattr(
        sys,
        "argv",
        ["sprint-publish-cards.py", "demo", "0.2.0", "--no-epic", "--no-carryover"],
    )

    with pytest.raises(SystemExit) as exc:
        publish.main()

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "is an epic" in err
    assert "source_epic: 260101-0001" in err


def test_publish_creates_new_task_under_source_epic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publish = load_script(
        "sprint_publish_source_epic_under_test",
        "kangnam-dev/scripts/sprint/sprint-publish-cards.py",
    )
    kanban_root = init_kanban_root(tmp_path)
    planning_dir = tmp_path / "wiki" / "Projects" / "demo" / "Sprints" / "0.2.0"
    planning_dir.mkdir(parents=True)
    (planning_dir / "planning.md").write_text(
        """---
project: demo
sprint: 0.2.0
---

## 한 줄 요약

결제 정리

## Core Gates

### G1. 결제 실패 메시지 통일
- **domain**: `backend`
- **card**: `new`
- **source_epic**: `260101-0001`
- **happy** — ok
  - 검증: `manual`
- **isolation_failure** — fail
  - 검증: `manual`
- **expected_reaction** — react
  - 검증: `manual`
""",
        encoding="utf-8",
    )
    write_card(
        kanban_root / "Backlog" / "payment-epic.md",
        {
            "id": "260101-0001",
            "created": "2026-01-01T00:01:00+09:00",
            "title": "결제 구조 개선",
            "project": "demo",
            "type": "epic",
        },
    )
    created_args: list[tuple[str, ...]] = []

    def fake_new(*args: str) -> str:
        created_args.append(args)
        return "260101-0002"

    monkeypatch.setattr(publish, "KANBAN_ROOT", kanban_root)
    monkeypatch.setattr(publish, "project_dir", lambda project: tmp_path / "wiki" / "Projects" / project)
    monkeypatch.setattr(publish, "normalize_version", lambda project, version: version)
    monkeypatch.setattr(publish, "sprint_dir", lambda project, version: planning_dir)
    monkeypatch.setattr(publish, "run_kanban_new", fake_new)
    monkeypatch.setattr(publish, "run_kanban_set", lambda *args: pytest.fail("must not set existing card"))
    monkeypatch.setattr(
        sys,
        "argv",
        ["sprint-publish-cards.py", "demo", "0.2.0", "--no-epic", "--no-carryover"],
    )

    publish.main()

    assert len(created_args) == 1
    args = created_args[0]
    assert "--type" in args
    assert args[args.index("--type") + 1] == "task"
    assert "--epic" in args
    assert args[args.index("--epic") + 1] == "260101-0001"


def test_sprint_implement_ignores_epic_cards_when_building_dispatch_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sprint_implement = load_script(
        "sprint_implement_under_test",
        "kangnam-dev/scripts/sprint/sprint-implement.py",
    )
    wiki_root = tmp_path / "wiki"
    kanban_root = init_kanban_root(tmp_path)
    monkeypatch.setattr(sprint_implement, "WIKI_ROOT", wiki_root)
    write_card(
        kanban_root / "Backlog" / "task.md",
        {
            "id": "260101-0001",
            "created": "2026-01-01T00:01:00+09:00",
            "title": "로그인 실패 메시지 수정",
            "project": "demo",
            "sprint": "0.2.0",
            "gate": "G1",
        },
    )
    write_card(
        kanban_root / "Backlog" / "epic.md",
        {
            "id": "260101-0002",
            "created": "2026-01-01T00:02:00+09:00",
            "title": "결제 구조 개선",
            "project": "demo",
            "sprint": "0.2.0",
            "type": "epic",
        },
    )

    cards = sprint_implement.sprint_cards("demo", "0.2.0")

    assert [card["id"] for card in cards] == ["260101-0001"]
    assert cards[0]["gate"] == "G1"


def test_publish_then_implement_dispatches_adopted_task_and_epic_child_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    publish = load_script(
        "sprint_publish_full_under_test",
        "kangnam-dev/scripts/sprint/sprint-publish-cards.py",
    )
    sprint_implement = load_script(
        "sprint_implement_full_under_test",
        "kangnam-dev/scripts/sprint/sprint-implement.py",
    )
    kanban_root = init_kanban_root(tmp_path)
    planning_dir = tmp_path / "wiki" / "Projects" / "demo" / "Sprints" / "0.2.0"
    write_planning(
        planning_dir / "planning.md",
        """### G1. 로그인 실패 메시지 수정
- **domain**: `backend`
- **card**: `260101-0001`
- **source_epic**: `none`
- **happy** — 잘못된 비밀번호 입력 시 401 응답을 반환한다
  - 검증: `manual`
- **isolation_failure** — 인증 저장소가 응답하지 않는다
  - 검증: `manual`
- **expected_reaction** — 503과 Retry-After 헤더를 반환한다
  - 검증: `manual`

### G2. 결제 실패 메시지 통일
- **domain**: `backend`
- **card**: `new`
- **source_epic**: `260101-0002`
- **happy** — 결제 실패 응답 형식을 표준 에러 스키마로 반환한다
  - 검증: `manual`
- **isolation_failure** — 결제 게이트웨이가 502를 반환한다
  - 검증: `manual`
- **expected_reaction** — 내부 표준 에러 코드와 사용자 메시지를 반환한다
  - 검증: `manual`
""",
    )
    write_progress(planning_dir / "progress.md", checked=False)
    task_path = kanban_root / "Backlog" / "login-message.md"
    epic_path = kanban_root / "Backlog" / "payment-epic.md"
    write_card(
        task_path,
        {
            "id": "260101-0001",
            "created": "2026-01-01T00:01:00+09:00",
            "title": "로그인 실패 메시지 수정",
            "project": "demo",
        },
    )
    write_card(
        epic_path,
        {
            "id": "260101-0002",
            "created": "2026-01-01T00:02:00+09:00",
            "title": "결제 구조 개선",
            "project": "demo",
            "type": "epic",
        },
    )

    def fake_set(card_id: str, *args: str) -> None:
        target = task_path if card_id == "260101-0001" else epic_path
        fm = read_frontmatter(target)
        for i in range(0, len(args), 2):
            key = args[i].removeprefix("--")
            value = args[i + 1]
            fm[key] = value
        write_card(target, fm)

    def fake_new(*args: str) -> str:
        title = args[0]
        fm = {"id": "260101-0003", "created": "2026-01-01T00:03:00+09:00", "title": title}
        for i in range(1, len(args), 2):
            key = args[i].removeprefix("--")
            value = args[i + 1]
            if key == "type" and value == "task":
                continue
            fm[key] = value
        write_card(kanban_root / "Backlog" / "payment-child.md", fm)
        return "260101-0003"

    for module in (publish, sprint_implement):
        monkeypatch.setattr(module, "WIKI_ROOT", tmp_path / "wiki")
    monkeypatch.setattr(publish, "KANBAN_ROOT", kanban_root)
    monkeypatch.setattr(publish, "project_dir", lambda project: tmp_path / "wiki" / "Projects" / project)
    monkeypatch.setattr(publish, "normalize_version", lambda project, version: version)
    monkeypatch.setattr(publish, "sprint_dir", lambda project, version: planning_dir)
    monkeypatch.setattr(publish, "run_kanban_set", fake_set)
    monkeypatch.setattr(publish, "run_kanban_new", fake_new)
    monkeypatch.setattr(sys, "argv", ["sprint-publish-cards.py", "demo", "0.2.0", "--no-epic", "--no-carryover"])

    publish.main()

    assert read_frontmatter(task_path)["sprint"] == "0.2.0"
    assert read_frontmatter(task_path)["gate"] == "G1"
    child_fm = read_frontmatter(kanban_root / "Backlog" / "payment-child.md")
    assert child_fm["sprint"] == "0.2.0"
    assert child_fm["gate"] == "G2"
    assert child_fm["epic"] == "260101-0002"

    monkeypatch.setattr(sprint_implement, "project_dir", lambda project: tmp_path / "wiki" / "Projects" / project)
    monkeypatch.setattr(sprint_implement, "normalize_version", lambda project, version: version)
    monkeypatch.setattr(sprint_implement, "sprint_dir", lambda project, version: planning_dir)
    monkeypatch.setattr(sys, "argv", ["sprint-implement.py", "demo", "0.2.0", "--json"])
    publish_stdout = capsys.readouterr()

    sprint_implement.main()
    report = json.loads(capsys.readouterr().out)

    assert "기존 카드 연결" in publish_stdout.out
    assert report["dispatch_count"] == 2
    assert report["incomplete_count"] == 0
    assert [gate["card"]["id"] for gate in report["dispatch"]] == ["260101-0001", "260101-0003"]


def test_progress_freeze_and_review_require_done_cards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    progress = load_script(
        "sprint_progress_review_under_test",
        "kangnam-dev/scripts/sprint/sprint-progress.py",
    )
    review = load_script(
        "sprint_review_under_test",
        "kangnam-dev/scripts/sprint/sprint-review.py",
    )
    kanban_root = init_kanban_root(tmp_path)
    project_root = tmp_path / "wiki" / "Projects" / "demo"
    planning_dir = project_root / "Sprints" / "0.2.0"
    write_planning(
        planning_dir / "planning.md",
        """### G1. 로그인 실패 메시지 수정
- **domain**: `backend`
- **card**: `260101-0001`
- **source_epic**: `none`
- **happy** — 잘못된 비밀번호 입력 시 401 응답을 반환한다
  - 검증: `manual`
- **isolation_failure** — 인증 저장소가 응답하지 않는다
  - 검증: `manual`
- **expected_reaction** — 503과 Retry-After 헤더를 반환한다
  - 검증: `manual`
""",
    )
    progress_path = planning_dir / "progress.md"
    write_progress(progress_path, checked=True)
    write_card(
        kanban_root / "Backlog" / "login-message.md",
        {
            "id": "260101-0001",
            "created": "2026-01-01T00:01:00+09:00",
            "title": "로그인 실패 메시지 수정",
            "project": "demo",
            "sprint": "0.2.0",
            "gate": "G1",
        },
    )

    monkeypatch.setattr(progress, "git_add", lambda *paths: None)
    progress.freeze(progress_path, force=False)
    assert read_frontmatter(progress_path)["status"] == "evergreen"

    for module in (review,):
        monkeypatch.setattr(module, "WIKI_ROOT", tmp_path / "wiki")
        monkeypatch.setattr(module, "project_dir", lambda project: project_root)
        monkeypatch.setattr(module, "normalize_version", lambda project, version: version)
        monkeypatch.setattr(module, "sprint_dir", lambda project, version: planning_dir)
        monkeypatch.setattr(module, "git_add", lambda *paths: None)

    monkeypatch.setattr(sys, "argv", ["sprint-review.py", "demo", "0.2.0"])
    with pytest.raises(SystemExit) as blocked:
        review.main()
    assert blocked.value.code == 2

    done_path = kanban_root / "Done" / "login-message.md"
    done_path.write_text((kanban_root / "Backlog" / "login-message.md").read_text(encoding="utf-8"), encoding="utf-8")
    (kanban_root / "Backlog" / "login-message.md").unlink()

    monkeypatch.setattr(sys, "argv", ["sprint-review.py", "demo", "0.2.0"])
    review.main()

    review_path = planning_dir / "review.md"
    assert review_path.is_file()
    assert read_frontmatter(review_path)["status"] == "growing"


def test_full_sprint_cli_flow_with_tmp_wiki(tmp_path: Path) -> None:
    home = tmp_path / "home"
    wiki = home / "wiki"
    project_root = wiki / "Projects" / "demo"
    project_root.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=wiki, check=True, capture_output=True, text=True)

    run_cli(home, "kangnam-dev/skills/kanban/scripts/kanban-init.py")
    task_id = parse_added_id(
        run_cli(
            home,
            "kangnam-dev/skills/kanban/scripts/kanban-new.py",
            "로그인 실패 메시지 수정",
            "--project",
            "demo",
            "--type",
            "task",
        ).stdout
    )
    epic_id = parse_added_id(
        run_cli(
            home,
            "kangnam-dev/skills/kanban/scripts/kanban-new.py",
            "결제 구조 개선",
            "--project",
            "demo",
            "--type",
            "epic",
        ).stdout
    )

    run_cli(
        home,
        "kangnam-dev/scripts/sprint/sprint-planning.py",
        "demo",
        "0.2.0",
        "로그인과 결제 실패 흐름을 실제 명령으로 검증",
    )
    sprint_root = project_root / "Sprints" / "0.2.0"
    planning_path = sprint_root / "planning.md"
    planning_text = planning_path.read_text(encoding="utf-8")
    assert f"[{task_id}] 로그인 실패 메시지 수정" in planning_text
    assert f"[{epic_id}] 결제 구조 개선" in planning_text
    assert "reason: needs-breakdown-epic" in planning_text

    gates = f"""## Core Gates

### G1. 로그인 실패 메시지 수정
- **domain**: `backend`
- **card**: `{task_id}`
- **source_epic**: `none`
- **happy** — 잘못된 비밀번호 입력 시 401 응답을 반환한다
  - 검증: `manual`
- **isolation_failure** — 인증 저장소가 응답하지 않는다
  - 검증: `manual`
- **expected_reaction** — 503과 Retry-After 헤더를 반환한다
  - 검증: `manual`

### G2. 결제 실패 메시지 통일
- **domain**: `backend`
- **card**: `new`
- **source_epic**: `{epic_id}`
- **happy** — 결제 실패 응답 형식을 표준 에러 스키마로 반환한다
  - 검증: `manual`
- **isolation_failure** — 결제 게이트웨이가 502를 반환한다
  - 검증: `manual`
- **expected_reaction** — 내부 표준 에러 코드와 사용자 메시지를 반환한다
  - 검증: `manual`

## Out-of-scope"""
    planning_path.write_text(
        re.sub(r"## Core Gates\n.*?## Out-of-scope", gates, planning_text, flags=re.S),
        encoding="utf-8",
    )

    publish_out = run_cli(
        home,
        "kangnam-dev/scripts/sprint/sprint-publish-cards.py",
        "demo",
        "0.2.0",
        "--no-epic",
        "--no-carryover",
    ).stdout
    assert f"기존 카드 연결: [{task_id}]" in publish_out
    assert "updated " not in publish_out
    child_id = parse_published_gate_id(publish_out, "G2")

    implementation = json.loads(
        run_cli(home, "kangnam-dev/scripts/sprint/sprint-implement.py", "demo", "0.2.0", "--json").stdout
    )
    assert implementation["dispatch_count"] == 2
    assert implementation["incomplete_count"] == 0
    assert [gate["card"]["id"] for gate in implementation["dispatch"]] == [task_id, child_id]

    progress_path = sprint_root / "progress.md"
    progress_text = progress_path.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"- \[ \] \*\*(happy|isolation_failure|expected_reaction)\*\* — <검증 메모, 날짜>",
        r"- [x] **\1** — 실제 CLI 스프린트 흐름에서 충분한 검증을 완료함 2026-05-10",
        progress_text,
    )
    progress_path.write_text(progress_text, encoding="utf-8")

    run_cli(home, "kangnam-dev/skills/kanban/scripts/kanban-move.py", task_id, "done")
    run_cli(home, "kangnam-dev/skills/kanban/scripts/kanban-move.py", child_id, "done")
    run_cli(home, "kangnam-dev/scripts/sprint/sprint-progress.py", "demo", "0.2.0", "--freeze")
    assert read_frontmatter(progress_path)["status"] == "evergreen"

    run_cli(home, "kangnam-dev/scripts/sprint/sprint-review.py", "demo", "0.2.0")
    review_path = sprint_root / "review.md"
    assert review_path.is_file()
    assert read_frontmatter(review_path)["status"] == "growing"

    done_report = json.loads(
        run_cli(home, "kangnam-dev/scripts/sprint/sprint-implement.py", "demo", "0.2.0", "--json").stdout
    )
    assert done_report["dispatch_count"] == 0
    assert done_report["skipped_done_count"] == 2
