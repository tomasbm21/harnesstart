"""CLI: doctor, list, select, install, run. Never prints secrets."""

from __future__ import annotations

import argparse
import json
import os
import sys
import unittest

from . import __version__
from .base import BrainError, MissingApiKey, UnknownBrain
from .config import KNOWN_BRAINS, load_config
from .doctor import doctor_payload, render_text
from .paths import product_dir
from .registry import get_brain, list_brains, select, selected, selected_id, selected_source
from .secrets import assert_no_secrets, redact


def dumps(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="claw-brains",
        description=(
            "Optional Norfront Claw brains on Linux cloud "
            "(OpenHands, OpenClaw, Goose). Prime Agent stays the default."
        ),
    )
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--json", action="store_true", help="JSON on stdout")
    parser.add_argument("--repo", default=None, help="harnesstart repo root (or set CLAW_REPO)")
    sub = parser.add_subparsers(dest="cmd")

    doc = sub.add_parser("doctor", help="Linux readiness for each brain; no keys required")
    doc.add_argument("brain", nargs="?", help="prime | openhands | openclaw | goose")
    doc.add_argument("--json", action="store_true")

    lst = sub.add_parser("list", help="Known brains (star = selected)")
    lst.add_argument("--json", action="store_true")

    sel = sub.add_parser("select", help="Persist the optional brain (CLAW_BRAIN env still wins)")
    sel.add_argument("brain", help="prime | openhands | openclaw | goose")
    sel.add_argument("--json", action="store_true")

    shown = sub.add_parser("selected", help="Show the selected brain and why")
    shown.add_argument("--json", action="store_true")

    inst = sub.add_parser("install", help="Official Linux installer for one optional brain")
    inst.add_argument("brain", help="openhands | openclaw | goose (prime: see product/claw)")
    inst.add_argument("--json", action="store_true")

    run = sub.add_parser("run", help="One-shot turn. Stubbed without a key (never ask in chat)")
    run.add_argument("prompt", nargs="+")
    run.add_argument("--brain", default=None, help="override selected brain")
    run.add_argument("--timeout", type=int, default=180)
    run.add_argument("--json", action="store_true")

    st = sub.add_parser("status", help="Selected brain + doctor summary")
    st.add_argument("--json", action="store_true")

    sub.add_parser("test", help="Run unit tests (offline, no vendor keys)")

    args = parser.parse_args(argv)
    if args.version or args.cmd == "version":
        _emit(__version__)
        return 0
    if not args.cmd:
        parser.print_help()
        return 2
    if args.repo:
        os.environ["CLAW_REPO"] = args.repo
    cfg = load_config()
    want_json = bool(getattr(args, "json", False))
    try:
        if args.cmd == "doctor":
            payload = doctor_payload(cfg, brain=args.brain)
            _emit(dumps(payload) if want_json else render_text(payload))
            return 0 if payload.get("ok") else 1
        if args.cmd == "list":
            current = selected_id(cfg)
            items = []
            for brain in list_brains(cfg):
                report = brain.doctor()
                items.append(
                    {
                        "id": report.id,
                        "name": report.name,
                        "role": report.role,
                        "selected": report.id == current,
                        "present": report.present,
                        "version": report.version,
                        "live_turn": report.live_turn,
                        "license": report.license,
                        "repo": report.repo,
                    }
                )
            if want_json:
                _emit(dumps({"product": "claw-brains", "selected": current, "brains": items}))
            else:
                lines = []
                for item in items:
                    star = "*" if item["selected"] else " "
                    state = item["version"] or "not installed"
                    lines.append(
                        f"{star} {item['id']:10}  {item['role']:8}  {item['name']:12}  {state}"
                    )
                _emit("\n".join(lines) + "\n")
            return 0
        if args.cmd == "select":
            resolved = select(args.brain, cfg)
            payload = {"ok": True, "selected": resolved, "source": "file"}
            _emit(dumps(payload) if want_json else f"selected {resolved} (CLAW_BRAIN env still wins)\n")
            return 0
        if args.cmd == "selected":
            brain_id, source = selected_source(cfg)
            payload = {"id": brain_id, "source": source, "default": "prime"}
            _emit(dumps(payload) if want_json else f"{brain_id}  source={source}\n")
            return 0
        if args.cmd == "install":
            brain = get_brain(args.brain, cfg)
            result = brain.install()
            payload = {
                "ok": result.ok,
                "brain": brain.spec.id,
                "returncode": result.returncode,
                "present": brain.which() is not None,
                "version": brain.version(),
                "stubbed": result.stubbed,
                "reason": result.reason,
                "detail": redact((result.stdout or "") + (result.stderr or "")).strip()[:800],
            }
            if want_json:
                _emit(dumps(payload))
            else:
                text = payload["detail"] or (
                    f"installed {brain.spec.id}" if result.ok else f"install failed ({result.returncode})"
                )
                _emit(text)
                if result.ok and payload["present"]:
                    _emit(f"{brain.spec.id} → {brain.which()}  {payload['version'] or ''}")
            return 0 if result.ok else result.returncode or 1
        if args.cmd == "run":
            prompt = " ".join(args.prompt)
            brain = get_brain(args.brain, cfg) if args.brain else selected(cfg)
            result = brain.run(prompt, timeout=args.timeout)
            payload = {
                "ok": result.ok,
                "brain": brain.spec.id,
                "returncode": result.returncode,
                "stubbed": result.stubbed,
                "reason": result.reason,
                "argv": list(result.argv),
                "stdout": redact(result.stdout),
                "stderr": redact(result.stderr),
            }
            if want_json:
                _emit(dumps(payload))
            else:
                text = result.stdout or result.stderr or f"exit {result.returncode}"
                _emit(text)
            return 0 if result.ok else result.returncode or 1
        if args.cmd == "status":
            payload = doctor_payload(cfg)
            if want_json:
                _emit(dumps(payload))
            else:
                _emit(render_text(payload))
            return 0 if payload.get("ok") else 1
        if args.cmd == "test":
            tests = product_dir() / "brains" / "tests"
            suite = unittest.defaultTestLoader.discover(str(tests), pattern="test_*.py")
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            return 0 if result.wasSuccessful() else 1
    except UnknownBrain as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 2
    except MissingApiKey as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 2
    except (BrainError, FileNotFoundError, ValueError) as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 1
    parser.print_help()
    return 2


def _emit(text: str) -> None:
    text = redact(text)
    assert_no_secrets(text)
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
