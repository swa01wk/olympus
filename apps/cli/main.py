"""`olympus` — start or check an Olympus project from the folder you are in.

    olympus start [--prd FILE] [--name NAME] [--yes] [--no-open]
    olympus status
    olympus open

Talks to a running Olympus (`make dev` in the Olympus checkout). Standard library only,
so it starts fast and never imports the backend.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from pathlib import Path
from typing import Any

from apps.cli.detect import Detection, detect, looks_secret

OLYMPUS_HOME = Path(__file__).resolve().parents[2]
API_URL = os.environ.get("OLYMPUS_API_URL", "http://127.0.0.1:8000").rstrip("/")
UI_URL = os.environ.get("OLYMPUS_UI_URL", "http://127.0.0.1:3010").rstrip("/")
TOKEN_FILE = Path(os.environ.get("OLYMPUS_TOKEN_FILE", OLYMPUS_HOME / "var/olympus/local-token"))

STATUS_LABELS = {
    "WORKING": "working",
    "NEEDS_YOU": "needs you",
    "BLOCKED": "stopped",
    "DONE": "done",
    "OFF": "paused",
}


class CliError(Exception):
    pass


# --- talking to Olympus -----------------------------------------------------------------


def _token() -> str:
    token = os.environ.get("OLYMPUS_API_TOKEN")
    if token:
        return token.strip()
    if not TOKEN_FILE.exists():
        raise CliError(
            f"No sign-in token found at {TOKEN_FILE}.\n"
            f"  Start Olympus first:  cd {OLYMPUS_HOME} && make dev"
        )
    return TOKEN_FILE.read_text().strip()


def api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{API_URL}{path}", data=data, method=method)
    request.add_header("Authorization", f"Bearer {_token()}")
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if method != "GET":
        request.add_header("Idempotency-Key", str(uuid.uuid4()))
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read() or b"{}")
        except json.JSONDecodeError:
            payload = {}
        if exc.code == 404:
            return None
        message = payload.get("message") or payload.get("detail") or exc.reason
        raise CliError(f"Olympus said: {message}") from exc
    except urllib.error.URLError as exc:
        raise CliError(
            f"Olympus isn't running at {API_URL}.\n"
            f"  Start it in another terminal:  cd {OLYMPUS_HOME} && make dev"
        ) from exc


def check_signed_in() -> None:
    """Make sure we reach Olympus and it accepts our token before changing anything."""
    try:
        me = api("GET", "/actors/me")
    except CliError as exc:
        if "token" in str(exc).lower() or "unauthenticated" in str(exc).lower():
            raise CliError(
                f"Olympus at {API_URL} did not accept the sign-in token in {TOKEN_FILE}.\n"
                f"  Restart Olympus so it signs you in again:  cd {OLYMPUS_HOME} && make dev"
            ) from exc
        raise
    if not isinstance(me, dict) or "id" not in me and "actor_id" not in me:
        raise CliError(f"Something at {API_URL} answered, but it doesn't look like Olympus.")


def find_project(folder: Path) -> dict[str, Any] | None:
    found = api("GET", f"/local-projects?{urllib.parse.urlencode({'path': str(folder)})}")
    return found if isinstance(found, dict) else None


def run_url(cycle_id: str) -> str:
    return f"{UI_URL}/runs/{cycle_id}"


# --- prompts ----------------------------------------------------------------------------


def confirm(question: str, *, assume_yes: bool, default: bool = False) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        return default
    hint = "[Y/n]" if default else "[y/N]"
    answer = input(f"{question} {hint} ").strip().lower()
    return default if not answer else answer in ("y", "yes")


def _git(folder: Path, *args: str) -> None:
    result = subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise CliError(f"git {' '.join(args)} failed: {result.stderr.strip()}")


# --- commands ---------------------------------------------------------------------------


def cmd_start(args: argparse.Namespace) -> int:
    folder = Path.cwd().resolve()
    check_signed_in()
    existing = find_project(folder)
    if existing is not None:
        print(f"This folder is already the Olympus project “{existing['name']}”.")
        return _show_project(existing, open_browser=not args.no_open)

    found = detect(folder, args.prd)
    name = args.name or folder.name
    if found.kind == "existing":
        return _start_existing(found, name, args)
    return _start_new(found, name, args)


def _start_existing(found: Detection, name: str, args: argparse.Namespace) -> int:
    print(f"Found existing code here ({found.code_count} files). Olympus will learn it first.")
    if not found.is_git or not found.has_commits:
        what = "isn't a git repository" if not found.is_git else "has no commits yet"
        print(f"\nThis folder {what}. Olympus works from committed code.")
        secrets = looks_secret(found.folder)
        if secrets:
            print("Not committing automatically: these look like secrets and would be committed:")
            for path in secrets[:5]:
                print(f"  {path}")
            print("Add them to .gitignore, commit your code, then run `olympus start` again.")
            return 1
        if not confirm("Create a commit with everything in this folder now?", assume_yes=args.yes):
            print("Nothing changed. Commit your code, then run `olympus start` again.")
            return 1
        if not found.is_git:
            _git(found.folder, "init")
        _git(found.folder, "add", "-A")
        _git(found.folder, "commit", "-m", "Initial commit (before Olympus)")
    elif found.dirty:
        print(
            "\nYou have uncommitted changes. Olympus will work from your last commit and "
            "won't see them."
        )
        if not confirm("Continue anyway?", assume_yes=args.yes, default=True):
            print("Nothing changed. Commit or stash, then run `olympus start` again.")
            return 1

    started = api(
        "POST",
        "/start",
        {"journey": "BROWNFIELD_ONBOARDING", "name": name, "local_path": str(found.folder)},
    )
    print(f"\nStarted “{name}”. Olympus copies your repo and never edits this folder.")
    print("It will ask you to confirm what it learned about the app.")
    return _after_start(started, open_browser=not args.no_open)


def _start_new(found: Detection, name: str, args: argparse.Namespace) -> int:
    if found.prd is None or not found.prd.is_file():
        where = f" ({found.prd})" if found.prd else ""
        print(f"This looks like a new project, but there is no PRD{where}.")
        print("Describe the app in PRD.md here (or pass --prd FILE), then run this again.")
        return 1
    prd_text = found.prd.read_text(errors="replace")
    if len(prd_text.strip()) < 40:
        print(f"{found.prd.name} is too short. Describe the app in a few sentences or more.")
        return 1
    shown = (
        found.prd.relative_to(found.folder) if found.prd.is_relative_to(found.folder) else found.prd
    )
    print(f"New project. Building it from {shown}.")
    started = api(
        "POST",
        "/start",
        {
            "journey": "GREENFIELD_BUILD",
            "name": name,
            "prd_title": found.prd.name,
            "prd_text": prd_text,
            "local_path": str(found.folder),
        },
    )
    if not found.is_git:
        # Only after Olympus accepted the start: a failed start leaves the folder untouched.
        _git(found.folder, "init")
        print("Set up git here so Olympus can hand the finished code back as a branch.")
    print(f"\nStarted “{name}”. When it's released, the code arrives here on an")
    print("`olympus/...` branch. Your own files are never touched.")
    return _after_start(started, open_browser=not args.no_open)


def _after_start(started: dict[str, Any], *, open_browser: bool) -> int:
    url = run_url(started["delivery_cycle_id"])
    autopilot = started.get("autopilot") or {}
    print(f"\n  Now: {autopilot.get('message', 'Starting')}")
    print(f"  Follow along: {url}")
    if open_browser:
        webbrowser.open(url)
    return 0


def _show_project(project: dict[str, Any], *, open_browser: bool) -> int:
    run = project.get("latest_run")
    if not run:
        print("It has no runs yet.")
        return 0
    autopilot = run["autopilot"]
    label = STATUS_LABELS.get(autopilot["status"], autopilot["status"].lower())
    print(f"  Status: {label} — {autopilot['message']}")
    url = run_url(run["delivery_cycle_id"])
    print(f"  Open: {url}")
    if open_browser:
        webbrowser.open(url)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    check_signed_in()
    project = find_project(Path.cwd().resolve())
    if project is None:
        print("This folder isn't an Olympus project yet. Run `olympus start` here.")
        return 1
    print(f"“{project['name']}”")
    return _show_project(project, open_browser=False)


def cmd_open(args: argparse.Namespace) -> int:
    check_signed_in()
    project = find_project(Path.cwd().resolve())
    if project is None:
        print("This folder isn't an Olympus project yet. Run `olympus start` here.")
        return 1
    return _show_project(project, open_browser=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="olympus", description="Build or change the project in this folder with Olympus."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="Start Olympus on this folder (new app or existing code)")
    start.add_argument("--prd", help="PRD file for a new app (default: PRD.md)")
    start.add_argument("--name", help="Project name (default: folder name)")
    start.add_argument("--yes", "-y", action="store_true", help="Answer yes to questions")
    start.add_argument("--no-open", action="store_true", help="Don't open the browser")
    start.set_defaults(func=cmd_start)
    status = sub.add_parser("status", help="Show what Olympus is doing for this folder")
    status.set_defaults(func=cmd_status)
    open_ = sub.add_parser("open", help="Open this folder's run in the browser")
    open_.set_defaults(func=cmd_open)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(line_buffering=True)
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except CliError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
