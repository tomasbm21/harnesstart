"""Closed WhatsApp preview. Allowlist only. iMessage stays unavailable."""

from __future__ import annotations

import os
import re

from norfront_claw.guards import check_text

_NUMBER = re.compile(r"^\+\d{8,15}$")


def imessage_available() -> bool:
    return False


def allowlist() -> set[str]:
    raw = os.environ.get("CLAW_WHATSAPP_ALLOWLIST") or ""
    numbers: set[str] = set()
    for part in raw.split(","):
        item = part.strip()
        if _NUMBER.match(item):
            numbers.add(item)
    return numbers


def handle_inbound(number: str, text: str, *, allow_irreversible: bool = False) -> dict:
    """Turn an allowlisted message into a crew task. Never send it onward."""
    if imessage_available():
        channel = "imessage"
    else:
        channel = "whatsapp"
    cleaned = number.strip()
    if cleaned not in allowlist():
        return {
            "ok": False,
            "channel": channel,
            "reason": "closed preview: number is not on the allowlist",
        }
    verdict = check_text(text, allow_irreversible=allow_irreversible)
    if not verdict.allowed:
        return {
            "ok": False,
            "channel": channel,
            "reason": verdict.reason,
            "approve": "Open the console and approve this before the crew runs.",
            "task": text,
        }
    return {
        "ok": True,
        "channel": channel,
        "task": text,
        "status": "queued",
    }
