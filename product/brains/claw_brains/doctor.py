"""Linux-cloud readiness for optional brains. Never prints secret values."""

from __future__ import annotations

import platform
import sys

from . import __version__
from .config import DEFAULT_BRAIN, Config, presence_label
from .registry import get_brain, list_brains, selected_source

STUBBED = (
    "live-model-turns",
    "r2-isolation",
    "hermes-kanban",
)


def doctor_payload(cfg: Config, *, brain: str | None = None) -> dict:
    system = platform.system()
    linux = system == "Linux"
    py = sys.version_info
    python_ok = py >= (3, 12)
    current, source = selected_source(cfg)
    if brain:
        brains = [get_brain(brain, cfg)]
    else:
        brains = list_brains(cfg)
    reports = [b.doctor().asdict() for b in brains]
    payload = {
        "product": "claw-brains",
        "version": __version__,
        "ok": linux and python_ok,
        "host": "linux" if linux else system.lower(),
        "default": DEFAULT_BRAIN,
        "selected": current,
        "selected_source": source,
        "workspace": str(cfg.workspace),
        "brains": reports,
        "keys": {
            "DEEPSEEK_API_KEY": presence_label(cfg.deepseek_key),
            "LLM_API_KEY": presence_label(cfg.llm_api_key),
            "OPENAI_API_KEY": presence_label(cfg.openai_key),
        },
        "stubbed": list(STUBBED),
        "isolation": (
            "These brains are host processes. Pair with product/vm for BRIEF R2. "
            "Prime Agent stays the default in product/claw."
        ),
        "hint": (
            "Select: ./product/brains/claw-brains select openhands|openclaw|goose "
            "(or CLAW_BRAIN=…). Default remains prime."
        ),
        "checks": [
            {
                "id": "linux",
                "ok": linux,
                "detail": f"{system} {platform.release()} {platform.machine()}",
                "warning": False,
            },
            {
                "id": "python",
                "ok": python_ok,
                "detail": f"Python {py.major}.{py.minor}.{py.micro}",
                "warning": False,
            },
        ],
    }
    return payload


def render_text(payload: dict) -> str:
    lines = [
        f"claw-brains {payload.get('version')}  "
        f"{'READY' if payload.get('ok') else 'NOT READY'}  host={payload.get('host')}",
        f"default     {payload.get('default')} (product/claw; not taken over)",
        f"selected    {payload.get('selected')}  source={payload.get('selected_source')}",
        f"workspace   {payload.get('workspace')}",
        "",
    ]
    for check in payload.get("checks", []):
        mark = "✓" if check["ok"] and not check.get("warning") else ("!" if check.get("warning") else "✗")
        lines.append(f"  {mark} {check['id']}: {check['detail']}")
    lines.append("")
    for brain in payload.get("brains", []):
        mark = "✓" if brain.get("present") else "!"
        star = "*" if brain.get("id") == payload.get("selected") else " "
        live = brain.get("live_turn")
        version = brain.get("version") or "not installed"
        lines.append(
            f"  {mark}{star} {brain.get('id'):10}  {brain.get('role'):8}  "
            f"{brain.get('name')}  {version}  live={live}"
        )
        if not brain.get("present"):
            lines.append(f"       {brain.get('install_hint')}")
    lines.append("")
    lines.append("  keys (values never printed):")
    for name, state in payload.get("keys", {}).items():
        lines.append(f"    {name}: {state}")
    lines.append("")
    lines.append("  " + str(payload.get("isolation")))
    lines.append("  still stubbed: " + ", ".join(payload.get("stubbed", [])))
    lines.append("  " + str(payload.get("hint")))
    return "\n".join(lines) + "\n"
