#!/usr/bin/env python3
"""Write a secret-free snapshot for the operator console.

Presence labels only (set or missing). Never prints key values.
Output is gitignored: product/ui/public/status.local.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

UI_DIR = Path(__file__).resolve().parent
PRODUCT = UI_DIR.parent
ROOT = PRODUCT.parent
OUT = UI_DIR / "public" / "status.local.json"

KEY_NAMES = (
    "DEEPSEEK_API_KEY",
    "TYPESAFE_API_KEY",
    "TEXT_MODEL_API_KEY",
    "WEB_API_KEY",
    "GH_TOKEN",
)
BRAINS = ("prime", "openhands", "openclaw", "goose")
PRESENCE = frozenset({"set", "missing"})


class StatusError(ValueError):
    """Snapshot refused because it was not secret-free."""


def _ensure_path() -> None:
    for entry in (str(PRODUCT), str(PRODUCT / "brains")):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def _clip(value: object, fallback: str = "") -> str:
    if not isinstance(value, str):
        return fallback
    text = " ".join(value.split())
    if not text:
        return fallback
    if len(text) > 240:
        return text[:239] + "…"
    return text


def _secret_values() -> list[str]:
    found: list[str] = []
    for name in KEY_NAMES:
        raw = os.environ.get(name, "").strip()
        if len(raw) >= 8:
            found.append(raw)
    return found


def assert_clean(snapshot: dict) -> None:
    secrets = _secret_values()
    if not secrets:
        return
    for text in _strings(snapshot):
        for secret in secrets:
            if secret in text:
                raise StatusError("status snapshot contained a secret value")


def _strings(obj: object):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _strings(value)


def _selected_brain() -> str:
    raw = (os.environ.get("CLAW_BRAIN") or "").strip().lower()
    aliases = {
        "prime-agent": "prime",
        "oh": "openhands",
        "open-hands": "openhands",
        "oc": "openclaw",
        "open-claw": "openclaw",
    }
    raw = aliases.get(raw, raw)
    if raw in BRAINS:
        return raw
    try:
        from claw_brains.registry import selected_id

        bid = selected_id()
        if bid in BRAINS:
            return bid
    except Exception:
        return "prime"
    return "prime"


def project_snapshot(payload: dict) -> dict:
    keys_in = payload.get("keys") if isinstance(payload.get("keys"), dict) else {}
    keys: dict[str, str] = {}
    for name in KEY_NAMES:
        state = keys_in.get(name, "missing")
        if state not in PRESENCE:
            raise StatusError(f"refusing key state for {name}")
        keys[name] = state

    checks = []
    for item in payload.get("checks") or []:
        if not isinstance(item, dict):
            continue
        checks.append(
            {
                "id": _clip(item.get("id"), "check"),
                "ok": bool(item.get("ok")),
                "warning": bool(item.get("warning")),
                "detail": _clip(item.get("detail")),
            }
        )

    vm_in = payload.get("vm") if isinstance(payload.get("vm"), dict) else {}
    backends = []
    for item in vm_in.get("backends") or []:
        if not isinstance(item, dict):
            continue
        ident = _clip(item.get("id") or item.get("name"))
        if not ident:
            continue
        backends.append(
            {
                "id": ident,
                "live_start": _clip(item.get("live_start"), "unknown"),
                "present": bool(item.get("present")),
                "selected": bool(item.get("selected")),
            }
        )

    brain = _selected_brain()
    snapshot = {
        "source": "local",
        "ok": bool(payload.get("ok")),
        "host": _clip(payload.get("host"), "linux"),
        "provider": _clip(payload.get("provider"), "deepseek"),
        "model": _clip(payload.get("model"), "deepseek-v4-pro"),
        "adapter": _clip(payload.get("adapter"), "missing-jev"),
        "keys": keys,
        "checks": checks,
        "stubbed": [
            _clip(item)
            for item in (payload.get("stubbed") or [])
            if isinstance(item, str) and item.strip()
        ],
        "vm": {
            "selected": _clip(vm_in.get("selected"), "qemu"),
            "selected_source": _clip(vm_in.get("selected_source"), "default"),
            "accel": _clip(vm_in.get("accel"), ""),
            "r2_vm_boundary": bool(vm_in.get("r2_vm_boundary")),
            "r2_hardware_kvm": bool(vm_in.get("r2_hardware_kvm")),
            "backends": backends,
        },
        "brains": [{"id": name, "selected": name == brain} for name in BRAINS],
        "browser": {
            "observe_needs_key": False,
            "guards_need_key": False,
            "choose_needs_key": True,
            "browse_needs_key": True,
        },
    }
    assert_clean(snapshot)
    return snapshot


def build_snapshot(root: Path | None = None) -> dict:
    _ensure_path()
    from norfront_claw.config import load_config
    from norfront_claw.doctor import report

    return project_snapshot(report(load_config(root)))


def main() -> int:
    _ensure_path()
    try:
        snapshot = build_snapshot(ROOT)
    except StatusError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
