"""Secret-free crew traces. Role, pass/fail, and paths only."""

from __future__ import annotations

import json
import re
from pathlib import Path

from norfront_claw.secrets import assert_no_secrets, looks_like_secret_dump, redact

_SK = re.compile(r"sk-[A-Za-z0-9]{8,}")


def trace_dir(data_home: Path) -> Path:
    return data_home / "crew" / "runs"


def scrub(text: str) -> str:
    out = redact(text)
    return _SK.sub("***", out)


def write_trace(data_home: Path, run_id: str, record: dict) -> Path:
    folder = trace_dir(data_home)
    folder.mkdir(parents=True, exist_ok=True)
    safe = _scrub_obj(record)
    body = json.dumps(safe, indent=2, sort_keys=True)
    if looks_like_secret_dump(body):
        raise ValueError("refusing to write a trace that looks like a secret")
    assert_no_secrets(body)
    path = folder / f"{run_id}.json"
    path.write_text(body + "\n", encoding="utf-8")
    return path


def _scrub_obj(value: object) -> object:
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [_scrub_obj(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _scrub_obj(item) for key, item in value.items()}
    return value
