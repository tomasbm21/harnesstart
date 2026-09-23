"""Model routing. Local OpenAI-compatible URL wins. Offline when nothing is configured."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Protocol

DEEPSEEK_URL = "https://api.deepseek.com/v1"


class Model(Protocol):
    name: str

    def complete(self, role: str, prompt: str) -> str: ...


class OfflineModel:
    """Deterministic stand-in. No network. Used when no endpoint is configured."""

    name = "offline"

    def complete(self, role: str, prompt: str) -> str:
        round_no = _field(prompt, "ROUND") or "1"
        task = _field(prompt, "TASK")
        if role == "orchestrator":
            assignments: list[dict[str, object]] = [
                {
                    "role": "writer",
                    "instruction": "Make the smallest edit that satisfies the task.",
                    "tests": [],
                }
            ]
            lowered = task.lower()
            if any(word in lowered for word in ("ui", "phone", "form", "screen")):
                assignments.append(
                    {
                        "role": "ui",
                        "instruction": "Touch only product/ui and keep the phone-width form.",
                        "tests": [],
                    }
                )
            return json.dumps({"assignments": assignments, "stop": False})
        if role == "writer":
            return json.dumps(
                {"files": [], "note": "offline writer left the tree unchanged"}
            )
        if role == "ui":
            return json.dumps(
                {
                    "files": [],
                    "phone_ok": True,
                    "note": "offline ui specialist checked the phone-width form",
                }
            )
        if role == "reviewer":
            if "reject-once" in task.lower() and round_no == "1":
                return json.dumps(
                    {
                        "pass": False,
                        "role": "reviewer",
                        "note": "missing a phone-width form",
                    }
                )
            return json.dumps(
                {"pass": True, "role": "reviewer", "note": "offline reviewer passed"}
            )
        if role == "learn":
            note = _field(prompt, "FAIL")
            if not note:
                return json.dumps({"line": ""})
            return json.dumps(
                {"line": f"When the reviewer says {note}, fix that before writing again."}
            )
        return json.dumps({"note": "unknown role"})


class HttpModel:
    """OpenAI-compatible chat. The key is a header, never part of the prompt log."""

    def __init__(self, base_url: str, model: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_id = model
        self.api_key = api_key
        self.name = model

    def complete(self, role: str, prompt: str) -> str:
        url = self.base_url + "/chat/completions"
        body = json.dumps(
            {
                "model": self.model_id,
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"You are the {role} role in a coding crew. "
                            "Reply with one JSON object and nothing else."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return json.dumps({"error": type(exc).__name__, "pass": False, "files": []})
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            return json.dumps({"error": "bad_response", "pass": False, "files": []})


def resolve_model() -> Model:
    """Local base URL wins. A remote key is used only when CLAW_CREW_REMOTE=1."""
    if _truthy(os.environ.get("CLAW_CREW_OFFLINE")):
        return OfflineModel()
    base = (os.environ.get("CLAW_CREW_BASE_URL") or "").strip()
    model = (
        os.environ.get("CLAW_CREW_MODEL")
        or os.environ.get("CLAW_MODEL")
        or "deepseek-v4-pro"
    ).strip()
    key = (
        os.environ.get("CLAW_CREW_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or ""
    ).strip()
    if base:
        return HttpModel(base, model, key)
    if key and _truthy(os.environ.get("CLAW_CREW_REMOTE")):
        remote = (os.environ.get("CLAW_CREW_REMOTE_URL") or DEEPSEEK_URL).strip()
        return HttpModel(remote, model, key)
    return OfflineModel()


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _field(prompt: str, name: str) -> str:
    prefix = name + "="
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""
