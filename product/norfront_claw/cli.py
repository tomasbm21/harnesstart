"""Linux-cloud entrypoint for Norfront Claw."""

from __future__ import annotations

import argparse
import json
import os
import sys
import unittest
from pathlib import Path

from . import __version__
from .brain import MissingApiKey, PrimeBrain, install_prime_agent
from .browser import (
    AdapterMissing,
    PolicyUnavailable,
    load_browser_adapter,
)
from .computer import HostComputer
from .config import Config, load_config
from .doctor import dumps, render_text, report
from .guards import check_text
from .paths import product_dir, repo_root
from .prompt_keys import ensure_boot_keys
from .secrets import assert_no_secrets, redact
from .swarm import snapshot
from crew.intake import intake_task
from crew.loop import run_crew
from crew.model import resolve_model
from crew.whatsapp import handle_inbound, imessage_available


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--no-prompt",
        action="store_true",
        default=argparse.SUPPRESS,
        help="do not prompt for missing keys (also CLAW_NO_KEY_PROMPT=1)",
    )
    parser = argparse.ArgumentParser(
        prog="claw",
        description="Norfront Claw on Linux cloud — Prime Agent brain, Jev browser hook.",
        parents=[shared],
    )
    parser.add_argument("--version", action="store_true", help="print product version")
    parser.add_argument("--repo", default=None, help="harnesstart repo root (or set CLAW_REPO)")
    sub = parser.add_subparsers(dest="cmd")

    doc = sub.add_parser(
        "doctor",
        parents=[shared],
        help="Linux readiness; observe/guards do not need TypeSafe",
    )
    doc.add_argument("--json", action="store_true")

    sub.add_parser("status", help="Prime Agent daemon + adapter + computer")
    sub.add_parser("install", help="Install Prime Agent via the official Linux installer")
    sub.add_parser("stop", help="Stop Prime Agent workers and supervisor")
    sub.add_parser("agents", help="List Prime Agent sessions (not Hermes kanban)")

    run = sub.add_parser(
        "run",
        parents=[shared],
        help="One-shot Prime Agent turn (needs DEEPSEEK_API_KEY in env)",
    )
    run.add_argument("prompt", nargs="+")
    run.add_argument("--timeout", type=int, default=180)

    obs = sub.add_parser("observe", help="Browser snapshot via Jev adapter; no TypeSafe key")
    obs.add_argument("url")
    obs.add_argument("--json", action="store_true")

    grd = sub.add_parser("guards", help="Local R6 broker + Jev guard checks; no TypeSafe key")
    grd.add_argument("--text", default="", help="optional intent text to classify")
    grd.add_argument("--json", action="store_true")

    brw = sub.add_parser(
        "browse",
        parents=[shared],
        help="Live Jev run() (TYPESAFE_API_KEY from env, never chat)",
    )
    brw.add_argument("url")
    brw.add_argument("goal", nargs="+")

    chs = sub.add_parser(
        "choose",
        parents=[shared],
        help="Jev choose() after observe (TYPESAFE_API_KEY from env)",
    )
    chs.add_argument("url")
    chs.add_argument("goal", nargs="+")
    chs.add_argument("--json", action="store_true")

    pol = sub.add_parser("policy", help="Jev policy_status booleans; never prints key values")
    pol.add_argument("--json", action="store_true")

    sub.add_parser("test", help="Run product unit tests (offline, no vendor keys)")
    sub.add_parser(
        "ui",
        parents=[shared],
        help="Open the Norfront Claw console in your browser",
    )
    crew = sub.add_parser(
        "crew",
        parents=[shared],
        help="Run orchestrator, writer, reviewer, and UI specialist",
    )
    crew.add_argument("task", nargs="*")
    crew.add_argument("--intake", default=None, help="folder of notes to turn into the task")
    crew.add_argument(
        "--from-number",
        default=None,
        help="closed WhatsApp preview: allowlisted number only",
    )
    crew.add_argument("--json", action="store_true")
    crew.add_argument("--rounds", type=int, default=2)

    args = parser.parse_args(argv)
    if args.version or args.cmd == "version":
        print(__version__)
        return 0
    if not args.cmd:
        sys.stdout.write(you_are_here_text())
        return 0
    if args.repo:
        os.environ["CLAW_REPO"] = args.repo
    if args.cmd == "ui":
        return _start_ui(repo_root())
    cfg = load_config()
    cfg = ensure_boot_keys(
        cfg,
        command=str(args.cmd),
        no_prompt=bool(getattr(args, "no_prompt", False)),
    )
    handlers = {
        "doctor": _cmd_doctor,
        "status": _cmd_status,
        "install": _cmd_install,
        "stop": _cmd_stop,
        "agents": _cmd_agents,
        "run": _cmd_run,
        "observe": _cmd_observe,
        "guards": _cmd_guards,
        "browse": _cmd_browse,
        "choose": _cmd_choose,
        "policy": _cmd_policy,
        "test": _cmd_test,
        "crew": _cmd_crew,
    }
    try:
        code = handlers[args.cmd](cfg, args)
        return code
    except PolicyUnavailable as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 2
    except (MissingApiKey, AdapterMissing) as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 1


def you_are_here_text(*, windows: bool | None = None) -> str:
    """Five-line landing help. First line is how to open the console."""
    if windows is None:
        windows = os.name == "nt"
    if windows:
        first = "Open the console: double-click Launch Claw.bat"
    else:
        first = "Open the console: ./launch    or    ./product/claw ui"
    lines = [
        first,
        "You are in Norfront Claw.",
        "The console is the product. It opens in your browser.",
        "Keys are optional. When you want them: ./product/claw doctor",
        "Other commands: ./product/claw --help",
    ]
    return "\n".join(lines) + "\n"


def _start_ui(root: Path) -> int:
    """Start the same console as Launch Claw.bat / ./launch. No key prompts."""
    one_liner = "cd product/ui && npm install && npm run dev"
    try:
        if os.name == "nt":
            script = root / "Launch Claw.bat"
            comspec = os.environ.get("COMSPEC") or "cmd.exe"
            os.execv(comspec, [comspec, "/c", str(script)])
        script = root / "launch"
        os.execv(str(script), [str(script)])
    except OSError:
        print(one_liner)
        os.chdir(root)
        os.execvp("bash", ["bash", "-lc", one_liner])
    return 1


def _emit(text: str) -> None:
    text = redact(text)
    assert_no_secrets(text)
    sys.stdout.write(text if text.endswith("\n") else text + "\n")


def _cmd_doctor(cfg: Config, args: argparse.Namespace) -> int:
    payload = report(cfg)
    body = dumps(payload) if args.json else render_text(payload)
    _emit(body)
    return 0 if payload.get("ok") else 1


def _cmd_status(cfg: Config, _args: argparse.Namespace) -> int:
    computer = HostComputer().doctor()
    adapter = load_browser_adapter(cfg)
    brain = PrimeBrain(cfg)
    view = snapshot(brain)
    lines = [
        f"brain     {brain.which() or 'prime-agent not installed'}  {brain.version() or ''}",
        f"computer  {computer['name']}  r2_isolated={computer['r2_isolated']}  kvm={computer['kvm']}",
        f"browser   {adapter.name}",
        f"workspace {cfg.workspace}",
        f"swarm     {view.detail}",
        f"stub      {view.stub}",
    ]
    try:
        adapter.close()
    except Exception:
        pass
    _emit("\n".join(lines) + "\n")
    return 0


def _cmd_install(_cfg: Config, _args: argparse.Namespace) -> int:
    print("Installing Prime Agent (official Linux installer)…")
    proc = install_prime_agent()
    out = redact((proc.stdout or "") + (proc.stderr or ""))
    if out.strip():
        sys.stdout.write(out if out.endswith("\n") else out + "\n")
    if proc.returncode != 0:
        print(f"installer exit {proc.returncode}", file=sys.stderr)
        return proc.returncode
    brain = PrimeBrain(load_config())
    path = brain.which()
    print(f"prime-agent → {path or 'not found on PATH (add ~/.local/bin)'}")
    if brain.version():
        print(brain.version())
    return 0 if path else 1


def _cmd_stop(cfg: Config, _args: argparse.Namespace) -> int:
    brain = PrimeBrain(cfg)
    if brain.which() is None:
        print("prime-agent not installed; nothing to stop")
        return 0
    _emit(brain.shutdown())
    return 0


def _cmd_agents(cfg: Config, _args: argparse.Namespace) -> int:
    brain = PrimeBrain(cfg)
    view = snapshot(brain)
    _emit(f"{view.detail}\n{view.stub}\n")
    return 0


def _cmd_run(cfg: Config, args: argparse.Namespace) -> int:
    prompt = " ".join(args.prompt)
    verdict = check_text(prompt, allow_irreversible=cfg.allow_irreversible)
    if not verdict.allowed:
        print(verdict.reason, file=sys.stderr)
        return 1
    brain = PrimeBrain(cfg)
    result = brain.run_print(prompt, timeout=args.timeout)
    _emit(result.stdout or result.stderr or f"exit {result.returncode}")
    return 0 if result.ok else result.returncode or 1


def _cmd_observe(cfg: Config, args: argparse.Namespace) -> int:
    adapter = load_browser_adapter(cfg)
    try:
        result = adapter.observe(args.url)
    finally:
        adapter.close()
    if result.used_typesafe:
        print("observe() used TypeSafe — that is a contract bug in the adapter", file=sys.stderr)
        return 1
    payload = {
        "ok": result.ok,
        "url": result.url,
        "adapter": result.adapter,
        "used_typesafe": result.used_typesafe,
        "actions": list(result.actions),
        "detail": result.detail,
    }
    if args.json:
        _emit(json.dumps(payload, indent=2))
    else:
        _emit(
            f"observe adapter={result.adapter} ok={result.ok} typesafe={result.used_typesafe}\n"
            f"{result.detail or (str(len(result.actions)) + ' actions')}\n"
        )
    return 0 if result.ok else 1


def _cmd_guards(cfg: Config, args: argparse.Namespace) -> int:
    text = args.text
    local = check_text(text, allow_irreversible=cfg.allow_irreversible) if text else check_text(
        "read the page title", allow_irreversible=False
    )
    adapter = load_browser_adapter(cfg)
    try:
        remote = adapter.check_guards()
    finally:
        adapter.close()
    if remote.used_typesafe:
        print("check_guards() used TypeSafe — that is a contract bug in the adapter", file=sys.stderr)
        return 1
    payload = {
        "ok": local.allowed and remote.ok,
        "used_typesafe": False,
        "local": {
            "allowed": local.allowed,
            "kind": local.kind,
            "reason": local.reason,
        },
        "jev": {
            "adapter": remote.adapter,
            "ok": remote.ok,
            "passed": remote.passed,
            "total": remote.total,
            "detail": remote.detail,
        },
    }
    if args.json:
        _emit(json.dumps(payload, indent=2))
    else:
        _emit(
            f"local R6: {'ok' if local.allowed else 'blocked'} ({local.reason})\n"
            f"jev guards: adapter={remote.adapter} {remote.passed}/{remote.total} "
            f"typesafe={remote.used_typesafe}\n{remote.detail}\n"
        )
    return 0 if payload["ok"] else 1


def _cmd_browse(cfg: Config, args: argparse.Namespace) -> int:
    goal = " ".join(args.goal)
    verdict = check_text(goal, allow_irreversible=cfg.allow_irreversible)
    if not verdict.allowed:
        print(verdict.reason, file=sys.stderr)
        return 1
    adapter = load_browser_adapter(cfg)
    try:
        for event in adapter.run_policy(args.url, goal):
            _emit(json.dumps(event, default=str))
    finally:
        adapter.close()
    return 0


def _cmd_choose(cfg: Config, args: argparse.Namespace) -> int:
    goal = " ".join(args.goal)
    verdict = check_text(goal, allow_irreversible=cfg.allow_irreversible)
    if not verdict.allowed:
        print(verdict.reason, file=sys.stderr)
        return 1
    adapter = load_browser_adapter(cfg)
    try:
        observed = adapter.observe(args.url)
        if not observed.ok:
            _emit(json.dumps({"ok": False, "detail": observed.detail, "used_typesafe": False}))
            return 1
        decision = adapter.choose(observed.page or {"url": observed.url, "actions": list(observed.actions)}, goal)
    finally:
        adapter.close()
    if args.json:
        _emit(json.dumps(decision, default=str, indent=2))
    else:
        _emit(json.dumps(decision, default=str))
    return 0


def _cmd_policy(cfg: Config, args: argparse.Namespace) -> int:
    adapter = load_browser_adapter(cfg)
    try:
        status = adapter.policy_status()
    finally:
        adapter.close()
    _emit(json.dumps(status, indent=2, sort_keys=True))
    return 0


def _cmd_test(_cfg: Config, _args: argparse.Namespace) -> int:
    tests = product_dir() / "tests"
    suite = unittest.defaultTestLoader.discover(str(tests), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def _cmd_crew(cfg: Config, args: argparse.Namespace) -> int:
    text = " ".join(args.task).strip()
    if args.intake:
        notes = intake_task(Path(args.intake))
        text = (notes + ("\n\n" + text if text else "")).strip()
    if args.from_number:
        inbound = handle_inbound(
            args.from_number,
            text,
            allow_irreversible=cfg.allow_irreversible,
        )
        if not inbound.get("ok"):
            _emit(json.dumps({**inbound, "imessage": imessage_available()}))
            return 1
        text = str(inbound.get("task") or "")
    if not text:
        print("Give the crew a task, or pass --intake.", file=sys.stderr)
        return 2
    outcome = run_crew(
        text,
        repo=cfg.repo_root,
        model=resolve_model(),
        data_home=_crew_home(),
        rounds=args.rounds,
        allow_irreversible=cfg.allow_irreversible,
    )
    payload = outcome.public()
    payload["model"] = resolve_model().name
    payload["imessage"] = imessage_available()
    if args.json:
        _emit(json.dumps(payload, indent=2))
    else:
        lines = [
            f"crew {payload['model']} passed={payload['passed']} rounds={payload['rounds']}",
            "roles " + ", ".join(payload["roles"]),
            "files " + (", ".join(payload["files"]) or "(none)"),
            f"playbook_kept={payload['playbook_kept']}",
        ]
        if payload["blocked"]:
            lines.append(payload["blocked"])
        if payload["diff"]:
            lines.append(payload["diff"])
        _emit("\n".join(lines))
    if payload["blocked"]:
        return 1
    return 0 if payload["passed"] else 1


def _crew_home() -> Path:
    override = os.environ.get("CLAW_CREW_HOME")
    if override:
        return Path(override)
    from .paths import xdg_data_home

    return xdg_data_home() / "norfront-claw"
