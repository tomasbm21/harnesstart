"""Live Jev policy is env-only. Observe/guards do not use these keys."""

from __future__ import annotations

import os

# Names only. Never log, print, or return the values.
TYPESAFE_KEY = "TYPESAFE_API_KEY"
TEXT_KEY = "TEXT_MODEL_API_KEY"
TYPESAFE_MODEL = "TYPESAFE_MODEL"
TEXT_MODEL = "TEXT_MODEL"
TEXT_BASE = "TEXT_MODEL_BASE_URL"


class PolicyUnavailable(RuntimeError):
    """choose()/run() were called without the TypeSafe key in the environment."""


def _present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def policy_status() -> dict:
    """Booleans and non-secret model names. Key values are never included."""
    choose_ready = _present(TYPESAFE_KEY)
    type_text_ready = _present(TEXT_KEY)
    status = {
        "choose": choose_ready,
        "type_text": type_text_ready,
        "observe_needs_key": False,
        "guards_need_key": False,
    }
    if choose_ready:
        status["typesafe_model"] = os.environ.get(TYPESAFE_MODEL, "jev-latest")
    if type_text_ready:
        status["text_model"] = os.environ.get(TEXT_MODEL, "deepseek-chat")
        status["text_model_base_url"] = os.environ.get(TEXT_BASE, "https://api.deepseek.com/v1")
    return status


def require_choose() -> None:
    if _present(TYPESAFE_KEY):
        return
    raise PolicyUnavailable(
        "Live Jev choose()/run() need TYPESAFE_API_KEY in the environment "
        "(not chat). Observe and guards do not. TYPE_TEXT also needs "
        "TEXT_MODEL_API_KEY."
    )


def choose(page: dict, goal: str, history: list | None = None) -> dict:
    """TypeSafe operation/target. Blocked when TYPESAFE_API_KEY is unset."""
    require_choose()
    from jev_ultrafast.model import choose as jev_choose

    return jev_choose(page, goal, history or [])
