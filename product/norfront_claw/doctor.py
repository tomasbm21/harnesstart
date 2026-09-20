"""Linux-cloud readiness. Observe/guards checks never require TypeSafe."""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .brain import PrimeBrain
from .browser import load_browser_adapter
from .computer import HostComputer
from .config import Config, presence_label
from .guards import check_text

STUBBED = (
    "r2-vm-computer",
    "jev-adapter",
    "prime-bash-permission-extension",
    "hermes-kanban",
    "desktop-watch-takeover",
)


@dataclass
class Check:
    id: str
    ok: bool
    detail: str
    warning: bool = False


def _chrome_bin() -> str | None:
    for candidate in (
        os.environ.get("CHROME_BIN"),
        os.environ.get("CLAW_CHROME"),
        "/opt/google/chrome/chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ):
        if candidate and Path(candidate).exists():
            return candidate
    return shutil.which("google-chrome") or shutil.which("chromium")


def collect(cfg: Config) -> list[Check]:
    checks: list[Check] = []
    system = platform.system()
    checks.append(
        Check(
            "linux",
            system == "Linux",
            f"{system} {platform.release()} {platform.machine()}",
        )
    )
    py = sys.version_info
    checks.append(
        Check(
            "python",
            py >= (3, 11),
            f"Python {py.major}.{py.minor}.{py.micro}",
        )
    )
    computer = HostComputer()
    kvm = computer.kvm_present()
    checks.append(
        Check(
            "kvm",
            True,
            (
                "/dev/kvm present (unused: R2 computer is stubbed; Prime runs on the host)"
                if kvm
                else "/dev/kvm missing (R2 VM computer is stubbed either way)"
            ),
            warning=not kvm,
        )
    )
    brain = PrimeBrain(cfg)
    version = brain.version()
    checks.append(
        Check(
            "prime-agent",
            version is not None,
            version or "not on PATH — run ./product/claw install",
            warning=version is None,
        )
    )
    checks.append(
        Check(
            "deepseek",
            True,
            f"{presence_label(cfg.deepseek_key)} (needed for claw run, not for observe/guards)",
            warning=not cfg.deepseek_key,
        )
    )
    checks.append(
        Check(
            "typesafe",
            True,
            f"{presence_label(cfg.typesafe_key)} (live Jev policy only; observe/guards do not need it)",
            warning=False,
        )
    )
    adapter = load_browser_adapter(cfg)
    info = adapter.doctor()
    present = bool(info.get("present", adapter.name != "missing-jev"))
    checks.append(
        Check(
            "jev-adapter",
            True,
            f"{adapter.name}; present={present}; observe/guards typesafe=no",
            warning=not present,
        )
    )
    chrome = _chrome_bin()
    checks.append(
        Check(
            "chrome",
            True,
            chrome or "not found (Jev observe needs Chrome/CDP via product/jev)",
            warning=chrome is None,
        )
    )
    display = cfg.display or os.environ.get("DISPLAY") or ""
    checks.append(
        Check(
            "display",
            True,
            display or "DISPLAY unset (set BU_CDP_URL for a headless CDP browser)",
            warning=not display and not cfg.cdp_url,
        )
    )
    local = check_text("summarize this repo", allow_irreversible=False)
    checks.append(
        Check("r6-local-guards", local.allowed, local.reason),
    )
    workspace = cfg.workspace
    checks.append(
        Check(
            "workspace",
            True,
            f"{workspace} (Prime cwd; not the harness git tree)",
        )
    )
    try:
        adapter.close()
    except Exception:
        pass
    return checks


def report(cfg: Config) -> dict:
    checks = collect(cfg)
    hard_fail = [c for c in checks if not c.ok and not c.warning]
    ready = all(c.ok for c in checks if c.id in {"linux", "python"})
    adapter = load_browser_adapter(cfg)
    stubbed = [
        "r2-vm-computer",
        "prime-bash-permission-extension",
        "hermes-kanban",
        "desktop-watch-takeover",
    ]
    if adapter.name == "missing-jev":
        stubbed.insert(1, "jev-adapter")
    payload = {
        "ok": ready and not hard_fail,
        "ready": ready,
        "host": "linux" if platform.system() == "Linux" else platform.system().lower(),
        "provider": cfg.provider,
        "model": cfg.model,
        "workspace": str(cfg.workspace),
        "browser_profile": str(cfg.browser_profile),
        "adapter": adapter.name,
        "r2_isolated": False,
        "checks": [asdict(c) for c in checks],
        "stubbed": stubbed,
        "env_files": [str(p) for p in cfg.env_files],
        "keys": {
            "DEEPSEEK_API_KEY": presence_label(cfg.deepseek_key),
            "TYPESAFE_API_KEY": presence_label(cfg.typesafe_key),
            "TEXT_MODEL_API_KEY": presence_label(cfg.text_model_key),
            "WEB_API_KEY": presence_label(cfg.web_api_key),
            "GH_TOKEN": presence_label(cfg.gh_token),
        },
    }
    try:
        adapter.close()
    except Exception:
        pass
    return payload


def render_text(payload: dict) -> str:
    lines = [
        f"Norfront Claw Linux  {'READY' if payload.get('ok') else 'NOT READY'}",
        f"  brain     Prime Agent ({payload.get('provider')}/{payload.get('model')})",
        f"  computer  host process — R2 isolated={payload.get('r2_isolated')}",
        f"  browser   {payload.get('adapter')} (Jev hook)",
        "",
    ]
    for check in payload.get("checks", []):
        mark = "✓" if check["ok"] and not check.get("warning") else ("!" if check.get("warning") else "✗")
        lines.append(f"  {mark} {check['id']}: {check['detail']}")
    lines.append("")
    lines.append("  keys (values never printed):")
    for name, state in payload.get("keys", {}).items():
        lines.append(f"    {name}: {state}")
    lines.append("")
    lines.append("  still stubbed: " + ", ".join(payload.get("stubbed", [])))
    return "\n".join(lines) + "\n"


def dumps(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
