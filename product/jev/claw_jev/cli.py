"""CLI for the core and for Linux-cloud smoke: observe, guards, doctor, policy."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """setdefault from a file. Values are never printed."""
    if not path.is_file():
        raise FileNotFoundError(f"env file not found: {path}")
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _print_json(data) -> int:
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


def _observe(args) -> int:
    from claw_jev.session import ClawJev

    screenshot_path = Path(args.screenshot) if args.screenshot else None
    with ClawJev() as session:
        page = session.observe(args.url, screenshot=bool(screenshot_path))
    if screenshot_path and page.get("screenshot"):
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot_path.write_bytes(base64.b64decode(page["screenshot"]))
        page = {key: value for key, value in page.items() if key != "screenshot"}
        page["screenshot_file"] = str(screenshot_path)
    if args.json:
        return _print_json(page)
    actions = page.get("actions") or []
    print(f"url\t{page.get('url')}")
    print(f"title\t{page.get('title')}")
    print(f"actions\t{len(actions)}")
    for action in actions[:20]:
        kind = action.get("kind", "")
        label = action.get("label", "")
        print(f"  [{kind}] {label}")
    if screenshot_path:
        print(f"screenshot\t{screenshot_path}")
    return 0


def _guards(_args) -> int:
    from claw_jev.guards import check_guards

    report = check_guards()
    print(f"PASS: {report['passed']} browser guard checks; no model calls")
    if _args_json_flag(_args):
        return _print_json(report)
    for line in report["checks"]:
        print(line)
    return 0


def _args_json_flag(args) -> bool:
    return bool(getattr(args, "json", False))


def _doctor(args) -> int:
    from claw_jev.chrome import ChromeSession, doctor

    if args.start:
        ChromeSession().ensure()
    report = doctor()
    if args.json:
        return _print_json(report)
    print(f"chrome\t{report['chrome_binary'] or report['chrome_binary_error']}")
    print(f"user-data-dir\t{report['user_data_dir']}\tok={report['user_data_dir_ok']}")
    print(f"cdp\t{report['cdp_url']}\tok={report['cdp_ok']}\t{report['browser'] or ''}")
    print(f"no-sandbox\t{report['no_sandbox']}\theadless={report['headless']}\tDISPLAY={report['display']}")
    policy = report["policy"]
    print(f"observe/guards\tno TypeSafe key required")
    print(f"choose/run\tTYPESAFE_API_KEY set={policy['choose']}")
    print(f"TYPE_TEXT\tTEXT_MODEL_API_KEY set={policy['type_text']}")
    return 0 if report["user_data_dir_ok"] and report["chrome_binary"] else 1


def _policy(args) -> int:
    from claw_jev.policy import policy_status

    return _print_json(policy_status())


def _run(args) -> int:
    from claw_jev.policy import PolicyUnavailable
    from claw_jev.session import ClawJev

    try:
        with ClawJev() as session:
            last = None
            for state in session.run(args.url, args.goal):
                last = state
                print(f"{state['elapsed_ms']:>5} ms  {len(state['history'])} actions  {state['status']}")
            if last:
                print(last["page"]["url"])
        return 0
    except PolicyUnavailable as error:
        print(error, file=sys.stderr)
        return 2


def _stop(_args) -> int:
    from claw_jev.chrome import stop_chrome

    stop_chrome()
    print("stopped dedicated claw-jev Chrome (human profile untouched)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="claw-jev",
        description="Drive a dedicated Chrome via Jev. Observe/guards work without TypeSafe.",
    )
    parser.add_argument(
        "--env-file",
        help="Optional env file (setdefault). Do not paste keys in chat.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    observe = sub.add_parser("observe", help="Snapshot a URL (no TypeSafe)")
    observe.add_argument("url")
    observe.add_argument("--json", action="store_true")
    observe.add_argument("--screenshot", help="Write a JPEG; omitted from stdout JSON")
    observe.set_defaults(func=_observe)

    guards = sub.add_parser("guards", help="Local freshness/execution checks (no TypeSafe)")
    guards.add_argument("--json", action="store_true")
    guards.set_defaults(func=_guards)

    doctor = sub.add_parser("doctor", help="Chrome/CDP/profile/policy booleans")
    doctor.add_argument("--start", action="store_true", help="Launch dedicated Chrome first")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=_doctor)

    policy = sub.add_parser("policy", help="Whether choose()/TYPE_TEXT keys are set (no values)")
    policy.set_defaults(func=_policy)

    run = sub.add_parser("run", help="Live Jev loop (needs TYPESAFE_API_KEY in env)")
    run.add_argument("--url", required=True)
    run.add_argument("--goal", required=True)
    run.set_defaults(func=_run)

    stop = sub.add_parser("stop", help="Stop the dedicated claw-jev Chrome only")
    stop.set_defaults(func=_stop)

    args = parser.parse_args(argv)
    if args.env_file:
        _load_env_file(Path(args.env_file))
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
