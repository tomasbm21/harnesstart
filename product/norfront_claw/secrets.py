"""Redact secrets from any text that might be printed."""

from __future__ import annotations

import os
import re

from .config import SECRET_KEYS, is_present

_REDACTED = "***"


def secret_values() -> list[str]:
    values: list[str] = []
    for key in SECRET_KEYS:
        val = os.environ.get(key)
        if is_present(val) and val is not None and len(val) >= 4:
            values.append(val)
    return values


def redact(text: str) -> str:
    out = text
    for value in sorted(secret_values(), key=len, reverse=True):
        if value:
            out = out.replace(value, _REDACTED)
    return out


def assert_no_secrets(text: str) -> None:
    for value in secret_values():
        if value and value in text:
            raise AssertionError("refusing to emit a secret value")


def looks_like_secret_dump(text: str) -> bool:
    return bool(re.search(r"(sk-|api[_-]?key\s*=\s*\S{8})", text, re.I))
