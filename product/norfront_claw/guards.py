"""R6 local broker: irreversible actions need an explicit allow, never a chat paste."""

from __future__ import annotations

import re
from dataclasses import dataclass

# BRIEF R6: send, post, pay, delete, sign up.
_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "send",
        re.compile(
            r"\b(send|email|dm|message)\b.{0,40}\b(email|mail|tweet|sms|whatsapp|slack|discord)\b"
            r"|\b(send|post)\b.{0,20}\b(this|the)\b.{0,20}\b(email|message|tweet)\b",
            re.I,
        ),
    ),
    (
        "post",
        re.compile(
            r"\b(post|publish|tweet|toot)\b.{0,40}\b(twitter|x\.com|linkedin|facebook|instagram|public)\b"
            r"|\bpost (this|it) (live|publicly|to)\b",
            re.I,
        ),
    ),
    (
        "pay",
        re.compile(
            r"\b(pay|purchase|checkout|buy now|place order|wire transfer|donate)\b"
            r"|\benter (card|cvv|iban|routing)\b",
            re.I,
        ),
    ),
    (
        "delete",
        re.compile(
            r"\b(delete account|destroy (the )?prod|drop database|rm -rf /|shred (all|disk))\b"
            r"|\bpermanently delete\b",
            re.I,
        ),
    ),
    (
        "signup",
        re.compile(
            r"\b(sign up|signup|register account|create (an? )?account|open (an? )?account)\b",
            re.I,
        ),
    ),
)


@dataclass(frozen=True)
class GuardVerdict:
    allowed: bool
    kind: str | None
    reason: str
    used_typesafe: bool = False


def classify(text: str) -> str | None:
    blob = text.strip()
    if not blob:
        return None
    for kind, pattern in _RULES:
        if pattern.search(blob):
            return kind
    return None


def check_text(text: str, *, allow_irreversible: bool = False) -> GuardVerdict:
    kind = classify(text)
    if kind is None:
        return GuardVerdict(True, None, "no irreversible intent matched")
    if allow_irreversible:
        return GuardVerdict(
            True,
            kind,
            f"{kind} matched; allowed because CLAW_ALLOW_IRREVERSIBLE is set",
        )
    return GuardVerdict(
        False,
        kind,
        f"blocked {kind}: irreversible actions need CLAW_ALLOW_IRREVERSIBLE=1 "
        f"(put that in claw.env locally; do not paste keys in chat)",
    )
