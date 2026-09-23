"""What the writer and UI specialist may ask the browser to do.

observe and guards never need a TypeSafe key. choose and browse stay off
unless CLAW_BROWSER_LIVE is exactly 1.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_URL = re.compile(r"https?://[^\s)>\"]+")


def live_browser() -> bool:
    return (os.environ.get("CLAW_BROWSER_LIVE") or "").strip() == "1"


def browser_plan(task: str, *, role: str) -> dict:
    if role not in {"writer", "ui"}:
        return {"calls": [], "live": False, "used_typesafe": False}
    urls = _URL.findall(task)
    if not urls:
        return {"calls": [], "live": False, "used_typesafe": False}
    calls = ["observe", "guards"]
    live = live_browser()
    if live:
        calls.extend(["choose", "browse"])
    return {
        "calls": calls,
        "url": urls[0],
        "live": live,
        "used_typesafe": False,
    }


def execute_plan(plan: dict, repo: Path) -> dict:
    """Run observe and guards only when CLAW_CREW_BROWSER=1. Never live policy."""
    if (os.environ.get("CLAW_CREW_BROWSER") or "").strip() != "1" or not plan.get("calls"):
        return {**plan, "ran": False, "executed": []}
    from norfront_claw.browser import load_browser_adapter
    from norfront_claw.config import load_config

    root = repo if isinstance(repo, Path) else Path(repo)
    cfg = load_config(root)
    adapter = load_browser_adapter(cfg)
    executed: list[str] = []
    try:
        if "observe" in plan["calls"]:
            observed = adapter.observe(str(plan.get("url") or ""))
            if observed.used_typesafe:
                raise RuntimeError("observe must not use TypeSafe")
            executed.append("observe")
        if "guards" in plan["calls"]:
            guards = adapter.check_guards()
            if guards.used_typesafe:
                raise RuntimeError("guards must not use TypeSafe")
            executed.append("guards")
    finally:
        adapter.close()
    return {**plan, "ran": True, "executed": executed, "used_typesafe": False}
