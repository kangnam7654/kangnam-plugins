#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""CLI-first reviewers target review adapter for sprint gates and harnesses."""
from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path


PRESETS = (
    "grandma-70",
    "it-novice",
    "power-user",
    "impatient-mobile-user",
    "a11y-screen-reader",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run reviewers review-target and exit like a gate check."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--url", help="Web URL to review, e.g. http://127.0.0.1:3000")
    target.add_argument("--bundle-id", help="macOS app bundle id, e.g. com.apple.TextEdit")
    target.add_argument(
        "--running-app",
        nargs=2,
        metavar=("PID", "BUNDLE_ID"),
        help="Already-running macOS app target.",
    )
    target.add_argument(
        "--ios-simulator",
        nargs=2,
        metavar=("UDID", "BUNDLE_ID"),
        help="iOS Simulator target.",
    )

    persona = parser.add_mutually_exclusive_group()
    persona.add_argument("--persona-id", help="Existing reviewers persona UUID.")
    persona.add_argument(
        "--persona-preset",
        choices=PRESETS,
        default="it-novice",
        help="Built-in persona preset. Default: it-novice.",
    )

    parser.add_argument("--title", help="Optional task title.")
    parser.add_argument("--goal", required=True, help="Concrete user task for the persona.")
    parser.add_argument(
        "--success-criteria",
        required=True,
        help="Observable end state proving the task succeeded.",
    )
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--timeout-ms", type=int, default=600_000)
    parser.add_argument("--score-threshold", type=float, default=7.0)
    parser.add_argument("--username", help="Optional login username.")
    parser.add_argument("--password", help="Optional login password.")
    parser.add_argument(
        "--raw-mcp",
        action="store_true",
        help="Deprecated no-op kept for compatibility; this adapter is CLI-first.",
    )
    return parser.parse_args()


def reviewers_command() -> list[str]:
    configured = os.environ.get("REVIEWERS_CLI")
    if configured:
        return [configured]

    root = Path(os.environ.get("REVIEWERS_ROOT", str(Path.home() / "projects/reviewers")))
    local_bin = root / "target/debug/reviewers"
    if local_bin.is_file() and os.access(local_bin, os.X_OK):
        return [str(local_bin)]

    path_bin = shutil.which("reviewers")
    if path_bin:
        return [path_bin]

    return [
        "cargo",
        "run",
        "--manifest-path",
        str(root / "Cargo.toml"),
        "-p",
        "reviewers-cli",
        "--quiet",
        "--bin",
        "reviewers",
        "--",
    ]


def timeout_seconds(timeout_ms: int) -> int:
    if timeout_ms <= 0:
        return 0
    return int(math.ceil(timeout_ms / 1000))


def build_cli_args(args: argparse.Namespace) -> list[str]:
    cmd = reviewers_command()

    backend_url = os.environ.get("REVIEWERS_BACKEND_URL")
    if backend_url:
        cmd.extend(["--backend-url", backend_url])

    web_url = os.environ.get("REVIEWERS_WEB_URL")
    if web_url:
        cmd.extend(["--web-url", web_url])

    cmd.extend(["--json", "review-target"])

    if args.url is not None:
        cmd.extend(["--url", args.url])
    elif args.bundle_id is not None:
        cmd.extend(["--bundle-id", args.bundle_id])
    elif args.running_app is not None:
        cmd.extend(["--running-app", args.running_app[0], args.running_app[1]])
    else:
        cmd.extend(["--ios-simulator", args.ios_simulator[0], args.ios_simulator[1]])

    if args.title:
        cmd.extend(["--title", args.title])
    cmd.extend(["--goal", args.goal])
    cmd.extend(["--success-criteria", args.success_criteria])
    cmd.extend(["--max-steps", str(args.max_steps)])
    cmd.extend(["--timeout", str(timeout_seconds(args.timeout_ms))])
    cmd.extend(["--score-threshold", str(args.score_threshold)])

    if args.persona_id:
        cmd.extend(["--persona-id", args.persona_id])
    elif args.persona_preset:
        cmd.extend(["--persona-preset", args.persona_preset])

    if args.username or args.password:
        if not args.username or not args.password:
            raise SystemExit("--username and --password must be provided together")
        cmd.extend(["--username", args.username, "--password", args.password])

    return cmd


def main() -> None:
    args = parse_args()
    command = build_cli_args(args)
    proc = subprocess.run(command, text=True, check=False)
    raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
