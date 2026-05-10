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
AGENT_KANBAN = ROOT / "kangnam-dev" / "scripts" / "agent-kanban" / "agent-kanban.sh"


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


def run_agent(project_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(AGENT_KANBAN), *args, "--cwd", str(project_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"agent-kanban {' '.join(args)} failed with {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    fm_text = text.split("---", 2)[1]
    return yaml.safe_load(fm_text) or {}


def write_planning(path: Path, gates: str, summary: str = "스프린트 목표") -> None:
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

# demo — 0.2.0 Planning

## 한 줄 요약

{summary}

## Core Gates

{gates}
""",
        encoding="utf-8",
    )


def init_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    home = tmp_path / "home"
    wiki = home / "wiki"
    project_dir = tmp_path / "demo-project"
    (wiki / "Projects" / "demo").mkdir(parents=True)
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=wiki, check=True, capture_output=True, text=True)
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True, text=True)
    return home, wiki, project_dir


def agent_create(project_dir: Path, title: str, *, type_: str, **fields: str) -> dict:
    args = ["create", title, "--type", type_, "--project", "demo", "--status", fields.pop("status", "ready"), "--json"]
    for key, value in fields.items():
        args.extend([f"--{key.replace('_', '-')}", value])
    return json.loads(run_agent(project_dir, *args).stdout)


def test_agent_kanban_cli_uses_project_local_sprint_gate_metadata(tmp_path: Path) -> None:
    project_dir = tmp_path / "app"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True, text=True)

    epic = agent_create(project_dir, "결제 구조 개선", type_="epic", sprint="0.2.0")
    task = agent_create(project_dir, "결제 실패 메시지 통일", type_="task", epic=epic["id"], sprint="0.2.0", gate="G1")
    other_project = json.loads(
        run_agent(
            project_dir,
            "create",
            "다른 프로젝트 작업",
            "--type",
            "task",
            "--project",
            "other",
            "--status",
            "ready",
            "--sprint",
            "0.2.0",
            "--gate",
            "G1",
            "--json",
        ).stdout
    )
    assert (project_dir / ".kanban" / "kanban-data.json").is_file()

    listed = json.loads(run_agent(project_dir, "list", "--sprint", "0.2.0", "--gate", "G1", "--json").stdout)
    assert {card["id"] for card in listed["cards"]} == {task["id"], other_project["id"]}
    assert next(card for card in listed["cards"] if card["id"] == task["id"])["epicId"] == epic["id"]

    demo_listed = json.loads(run_agent(project_dir, "list", "--project", "demo", "--sprint", "0.2.0", "--gate", "G1", "--json").stdout)
    assert [card["id"] for card in demo_listed["cards"]] == [task["id"]]

    updated = json.loads(run_agent(project_dir, "set", task["id"], "--sprint", "0.3.0", "--gate", "G2", "--json").stdout)
    assert updated["sprint"] == "0.3.0"
    assert updated["gate"] == "G2"


def test_sprint_planning_intake_reads_project_local_task_and_epic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sprint_planning = load_script(
        "sprint_planning_under_test",
        "kangnam-dev/scripts/sprint/sprint-planning.py",
    )
    _, wiki, project_dir = init_workspace(tmp_path)
    monkeypatch.setattr(sprint_planning, "WIKI_ROOT", wiki)

    task = agent_create(project_dir, "로그인 실패 메시지 수정", type_="task")
    epic = agent_create(project_dir, "결제 구조 개선", type_="epic")

    intake = sprint_planning.build_sprint_intake("demo", "0.2.0", prev_sprint=None, working_dir=project_dir)

    assert f"[{task['id']}] 로그인 실패 메시지 수정" in intake
    assert "type: task" in intake
    assert f"[{epic['id']}] 결제 구조 개선" in intake
    assert "type: epic" in intake
    assert "reason: needs-breakdown-epic" in intake
    assert "`source_epic`" in intake


def test_publish_rejects_epic_as_direct_gate_card(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    publish = load_script(
        "sprint_publish_reject_under_test",
        "kangnam-dev/scripts/sprint/sprint-publish-cards.py",
    )
    home, wiki, project_dir = init_workspace(tmp_path)
    planning_dir = wiki / "Projects" / "demo" / "Sprints" / "0.2.0"
    epic = agent_create(project_dir, "결제 구조 개선", type_="epic")
    write_planning(
        planning_dir / "planning.md",
        f"""### G1. 결제 실패 메시지 통일
- **domain**: `backend`
- **card**: `{epic['id']}`
- **source_epic**: `none`
- **happy** — ok
  - 검증: `manual`
- **isolation_failure** — fail
  - 검증: `manual`
- **expected_reaction** — react
  - 검증: `manual`
""",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(publish, "project_dir", lambda project: wiki / "Projects" / project)
    monkeypatch.setattr(publish, "normalize_version", lambda project, version: version)
    monkeypatch.setattr(publish, "sprint_dir", lambda project, version: planning_dir)
    monkeypatch.setattr(sys, "argv", ["sprint-publish-cards.py", "demo", "0.2.0", "--working-dir", str(project_dir), "--no-epic", "--no-carryover"])

    with pytest.raises(SystemExit) as exc:
        publish.main()

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "is an epic" in err
    assert f"source_epic: {epic['id']}" in err


def test_publish_then_implement_dispatches_project_local_cards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    publish = load_script(
        "sprint_publish_full_under_test",
        "kangnam-dev/scripts/sprint/sprint-publish-cards.py",
    )
    sprint_implement = load_script(
        "sprint_implement_full_under_test",
        "kangnam-dev/scripts/sprint/sprint-implement.py",
    )
    home, wiki, project_dir = init_workspace(tmp_path)
    planning_dir = wiki / "Projects" / "demo" / "Sprints" / "0.2.0"
    task = agent_create(project_dir, "로그인 실패 메시지 수정", type_="task")
    epic = agent_create(project_dir, "결제 구조 개선", type_="epic")
    write_planning(
        planning_dir / "planning.md",
        f"""### G1. 로그인 실패 메시지 수정
- **domain**: `backend`
- **card**: `{task['id']}`
- **source_epic**: `none`
- **happy** — 잘못된 비밀번호 입력 시 401 응답을 반환한다
  - 검증: `manual`
- **isolation_failure** — 인증 저장소가 응답하지 않는다
  - 검증: `manual`
- **expected_reaction** — 503과 Retry-After 헤더를 반환한다
  - 검증: `manual`

### G2. 결제 실패 메시지 통일
- **domain**: `frontend`
- **card**: `new`
- **source_epic**: `{epic['id']}`
- **happy** — 결제 실패 화면에서 사용자가 원인을 이해한다
  - 검증: `{ROOT}/kangnam-dev/scripts/reviewers/review-target.py --url http://127.0.0.1:3000/checkout --goal "Trigger a payment failure" --success-criteria "A clear payment failure message is visible" --persona-preset it-novice --score-threshold 7`
- **isolation_failure** — 결제 게이트웨이가 502를 반환한다
  - 검증: `manual`
- **expected_reaction** — 내부 표준 에러 코드와 사용자 메시지를 반환한다
  - 검증: `manual`
""",
    )
    for module in (publish, sprint_implement):
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr(module, "project_dir", lambda project: wiki / "Projects" / project)
        monkeypatch.setattr(module, "normalize_version", lambda project, version: version)
        monkeypatch.setattr(module, "sprint_dir", lambda project, version: planning_dir)

    monkeypatch.setattr(sys, "argv", ["sprint-publish-cards.py", "demo", "0.2.0", "--working-dir", str(project_dir), "--no-epic", "--no-carryover"])
    publish.main()
    publish_stdout = capsys.readouterr().out
    assert f"기존 카드 연결: [{task['id']}]" in publish_stdout
    created_id = re.search(r"✓ G2 발행: \[(KBN-\d+)\]", publish_stdout)
    assert created_id

    monkeypatch.setattr(sys, "argv", ["sprint-implement.py", "demo", "0.2.0", "--working-dir", str(project_dir), "--json"])
    sprint_implement.main()
    report = json.loads(capsys.readouterr().out)

    assert report["dispatch_count"] == 2
    assert report["incomplete_count"] == 0
    assert [gate["card"]["id"] for gate in report["dispatch"]] == [task["id"], created_id.group(1)]
    assert "review-target.py" in report["dispatch"][1]["scenarios"]["happy"]["verification"]
    assert not (planning_dir / "progress.md").exists()


def test_full_sprint_cli_flow_with_project_local_kanban(tmp_path: Path) -> None:
    home, wiki, project_dir = init_workspace(tmp_path)
    task = agent_create(project_dir, "로그인 실패 메시지 수정", type_="task")
    epic = agent_create(project_dir, "결제 구조 개선", type_="epic")

    run_cli(
        home,
        "kangnam-dev/scripts/sprint/sprint-planning.py",
        "demo",
        "0.2.0",
        "프로젝트별 칸반과 reviewers 흐름 검증",
        "--working-dir",
        str(project_dir),
    )
    sprint_root = wiki / "Projects" / "demo" / "Sprints" / "0.2.0"
    planning_path = sprint_root / "planning.md"
    planning_text = planning_path.read_text(encoding="utf-8")
    assert f"[{task['id']}] 로그인 실패 메시지 수정" in planning_text
    assert f"[{epic['id']}] 결제 구조 개선" in planning_text

    gates = f"""## Core Gates

### G1. 로그인 실패 메시지 수정
- **domain**: `backend`
- **card**: `{task['id']}`
- **source_epic**: `none`
- **happy** — 잘못된 비밀번호 입력 시 401 응답을 반환한다
  - 검증: `manual`
- **isolation_failure** — 인증 저장소가 응답하지 않는다
  - 검증: `manual`
- **expected_reaction** — 503과 Retry-After 헤더를 반환한다
  - 검증: `manual`

### G2. 결제 실패 메시지 통일
- **domain**: `frontend`
- **card**: `new`
- **source_epic**: `{epic['id']}`
- **happy** — 결제 실패 화면에서 사용자가 원인을 이해한다
  - 검증: `{ROOT}/kangnam-dev/scripts/reviewers/review-target.py --url http://127.0.0.1:3000/checkout --goal "Trigger a payment failure" --success-criteria "A clear payment failure message is visible" --persona-preset it-novice --score-threshold 7`
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
        "--working-dir",
        str(project_dir),
        "--no-epic",
        "--no-carryover",
    ).stdout
    child_id = re.search(r"✓ G2 발행: \[(KBN-\d+)\]", publish_out)
    assert child_id

    implementation = json.loads(
        run_cli(
            home,
            "kangnam-dev/scripts/sprint/sprint-implement.py",
            "demo",
            "0.2.0",
            "--working-dir",
            str(project_dir),
            "--json",
        ).stdout
    )
    assert implementation["dispatch_count"] == 2
    assert [gate["card"]["id"] for gate in implementation["dispatch"]] == [task["id"], child_id.group(1)]

    run_agent(project_dir, "done", task["id"], "--summary", "G1 검증 완료")
    run_agent(project_dir, "done", child_id.group(1), "--summary", "G2 검증 완료")
    assert not (sprint_root / "progress.md").exists()

    run_cli(home, "kangnam-dev/scripts/sprint/sprint-review.py", "demo", "0.2.0", "--working-dir", str(project_dir))
    review_path = sprint_root / "review.md"
    assert review_path.is_file()
    assert read_frontmatter(review_path)["status"] == "growing"

    done_report = json.loads(
        run_cli(
            home,
            "kangnam-dev/scripts/sprint/sprint-implement.py",
            "demo",
            "0.2.0",
            "--working-dir",
            str(project_dir),
            "--json",
        ).stdout
    )
    assert done_report["dispatch_count"] == 0
    assert done_report["skipped_done_count"] == 2
