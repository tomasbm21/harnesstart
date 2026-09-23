"""Playbook edits stick only when the offline suite still passes."""

from __future__ import annotations

import re
from pathlib import Path

from norfront_claw.secrets import looks_like_secret_dump, redact

MAX_LEARNED = 40
_HEADER = (
    "# Norfront crew playbook\n"
    "# Learned lines only. Delete any line you do not want.\n"
)
_DENY = re.compile(
    r"skip tests|print the key|print the api|writer approves|send the |"
    r"\bpay\b|drop database|claw\.env",
    re.I,
)


def playbook_path(data_home: Path) -> Path:
    return data_home / "crew" / "playbook.md"


def load_playbook(data_home: Path) -> str:
    path = playbook_path(data_home)
    if not path.is_file():
        return _HEADER
    return path.read_text(encoding="utf-8")


def learned_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return lines


def line_is_safe(line: str) -> bool:
    cleaned = redact(line).strip()
    if not cleaned or "\n" in line or "\r" in line:
        return False
    if looks_like_secret_dump(cleaned):
        return False
    if _DENY.search(cleaned):
        return False
    if len(cleaned) > 200:
        return False
    return True


def run_regression(text: str) -> list[tuple[str, bool]]:
    """Five offline checks. No network and no keys."""
    learned = learned_lines(text)
    blob = "\n".join(learned)
    checks = [
        ("no_denied_instruction", _DENY.search(blob) is None),
        ("line_cap", len(learned) <= MAX_LEARNED),
        ("no_secret_material", not looks_like_secret_dump(blob)),
        ("single_lines", all("\n" not in line for line in learned)),
        ("writer_does_not_approve", "writer approves" not in blob.lower()),
    ]
    return checks


def suite_ok(text: str) -> bool:
    return all(ok for _, ok in run_regression(text))


def accept_line(data_home: Path, line: str) -> bool:
    """Append one line. Restore the previous file if the suite gets worse."""
    cleaned = redact(line).strip()
    if not line_is_safe(cleaned):
        return False
    path = playbook_path(data_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_text(encoding="utf-8") if path.is_file() else _HEADER
    if cleaned in learned_lines(previous):
        return False
    if len(learned_lines(previous)) >= MAX_LEARNED:
        return False
    updated = previous
    if not updated.endswith("\n"):
        updated += "\n"
    updated += cleaned + "\n"
    if not suite_ok(updated):
        return False
    path.write_text(updated, encoding="utf-8")
    if not suite_ok(path.read_text(encoding="utf-8")):
        path.write_text(previous, encoding="utf-8")
        return False
    return True
