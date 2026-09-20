"""Redact secrets from any text that might be printed. Never ask for keys in chat."""

from __future__ import annotations

import os
import re

_REDACTED = "***"

SECRET_KEYS = frozenset(
    {
        "DEEPSEEK_API_KEY",
        "WEB_API_KEY",
        "GH_TOKEN",
        "CLAW_JUDGE_API_KEY",
        "TYPESAFE_API_KEY",
        "TEXT_MODEL_API_KEY",
        "BROWSER_USE_API_KEY",
        "PRIME_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "TAVILY_API_KEY",
        "EXA_API_KEY",
        "FIRECRAWL_API_KEY",
        "CELESTO_API_KEY",
        "E2B_API_KEY",
        "E2B_ACCESS_TOKEN",
        "AENV_API_KEY",
        "AGENTENV_API_KEY",
    }
)

FORBIDDEN_FLAGS = frozenset(
    {
        "--api-key",
        "--apikey",
        "--e2b-api-key",
        "--celesto-api-key",
    }
)

STORED_IN_HERMES = "__stored_in_hermes__"


def is_present(value: str | None) -> bool:
    if not value:
        return False
    return value != STORED_IN_HERMES


def presence_label(name: str) -> str:
    return "set" if is_present(os.environ.get(name)) else "missing"


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


def refuse_secret_flags(argv: list[str]) -> list[str]:
    lowered = [a.lower() for a in argv]
    for flag in FORBIDDEN_FLAGS:
        if flag in lowered:
            raise RuntimeError("internal error: refusing to put an API key flag on argv")
    joined = " ".join(argv).lower()
    if "--api-key" in joined or "api_key=" in joined:
        raise RuntimeError("internal error: refusing to put an API key on argv")
    for value in secret_values():
        if value and value in " ".join(argv):
            raise RuntimeError("internal error: refusing to put a secret value on argv")
    return argv
