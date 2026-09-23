"""Turn a folder of notes into one internal crew task. Not a client login."""

from __future__ import annotations

from pathlib import Path

from norfront_claw.secrets import redact

_SUFFIXES = {".md", ".txt"}
_SKIP = {"claw.env", ".env"}
_CAP = 8000


def intake_task(folder: Path) -> str:
    notes: list[str] = []
    if folder.is_dir():
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            if path.name in _SKIP or path.name.startswith("."):
                continue
            if path.suffix.lower() not in _SUFFIXES:
                continue
            text = redact(path.read_text(encoding="utf-8", errors="replace"))
            notes.append(f"## {path.name}\n{text.strip()}")
    body = "\n\n".join(notes).strip()
    if len(body) > _CAP:
        body = body[:_CAP]
    if not body:
        body = "(no notes found)"
    return (
        "Scaffold an internal AI-native product from this company's notes. "
        "Leave irreversible actions for a person to approve.\n\n"
        + body
    )
