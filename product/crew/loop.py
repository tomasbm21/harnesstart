"""Orchestrator, writer, reviewer, UI specialist. Two review rounds, then stop."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from norfront_claw.guards import check_text
from norfront_claw.secrets import redact

from .browser_use import browser_plan, execute_plan
from .model import Model
from .playbook import accept_line, load_playbook
from .trace import write_trace

MAX_ROUNDS = 2
_BANNED_PREFIXES = ("swarm/souls/", "swarm/sealed/")


@dataclass
class CrewOutcome:
    ok: bool
    passed: bool
    blocked: str
    rounds: int
    roles: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    diff: str = ""
    playbook_kept: bool = False
    playbook_line: str = ""
    trace_path: str = ""
    browser: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def public(self) -> dict:
        return {
            "ok": self.ok,
            "passed": self.passed,
            "blocked": self.blocked,
            "rounds": self.rounds,
            "roles": self.roles,
            "files": self.files,
            "diff": self.diff,
            "playbook_kept": self.playbook_kept,
            "playbook_line": self.playbook_line,
            "trace": self.trace_path,
            "browser": self.browser,
            "notes": self.notes,
        }


def run_crew(
    task: str,
    *,
    repo: Path,
    model: Model,
    data_home: Path,
    rounds: int = MAX_ROUNDS,
    allow_irreversible: bool = False,
) -> CrewOutcome:
    verdict = check_text(task, allow_irreversible=allow_irreversible)
    if not verdict.allowed:
        return CrewOutcome(False, False, verdict.reason, 0)
    limit = max(1, min(rounds, MAX_ROUNDS))
    playbook = load_playbook(data_home)
    plan_raw = model.complete(
        "orchestrator",
        _prompt("orchestrator", task, playbook=playbook, round_no=1),
    )
    plan = _parse(plan_raw)
    assignments = [
        item
        for item in plan.get("assignments") or []
        if isinstance(item, dict) and item.get("role") in {"writer", "ui"}
    ]
    if not assignments:
        assignments = [{"role": "writer", "instruction": task, "tests": []}]
    roles = ["orchestrator"] + [str(item["role"]) for item in assignments] + ["reviewer"]
    notes: list[str] = []
    written: list[str] = []
    browsers: list[dict] = []
    passed = False
    used_rounds = 0
    before: dict[str, str] = {}
    for round_no in range(1, limit + 1):
        used_rounds = round_no
        for item in assignments:
            role = str(item["role"])
            browsers.append(execute_plan(browser_plan(task, role=role), repo))
            raw = model.complete(
                role,
                _prompt(
                    role,
                    task,
                    playbook=playbook,
                    round_no=round_no,
                    extra=str(item.get("instruction") or ""),
                    fail=" | ".join(notes),
                ),
            )
            data = _parse(raw)
            written.extend(_apply(repo, role, data.get("files") or [], before))
        review_raw = model.complete(
            "reviewer",
            _prompt(
                "reviewer",
                task,
                playbook=playbook,
                round_no=round_no,
                extra="\n".join(written),
                fail=" | ".join(notes),
            ),
        )
        review = _parse(review_raw)
        if review.get("role") not in {None, "reviewer"} or review.get("approved_by") == "writer":
            notes.append("writer cannot approve its own change")
            passed = False
            continue
        if review.get("pass") is True:
            passed = True
            notes.append(str(review.get("note") or "passed"))
            break
        passed = False
        notes.append(str(review.get("note") or "review failed"))
    line = ""
    kept = False
    fail_notes = [note for note in notes if note and "passed" not in note.lower()]
    if fail_notes:
        learned = model.complete(
            "learn",
            _prompt("learn", task, playbook=playbook, round_no=used_rounds, fail=fail_notes[-1]),
        )
        line = redact(str(_parse(learned).get("line") or "")).strip()
        if line:
            kept = accept_line(data_home, line)
            if not kept:
                line = ""
    run_id = uuid.uuid4().hex[:12]
    trace = write_trace(
        data_home,
        run_id,
        {
            "run": run_id,
            "passed": passed,
            "rounds": used_rounds,
            "roles": roles,
            "files": written,
            "notes": [redact(note) for note in notes],
            "playbook_kept": kept,
        },
    )
    return CrewOutcome(
        ok=True,
        passed=passed,
        blocked="",
        rounds=used_rounds,
        roles=roles,
        files=written,
        diff=_diff(repo, before),
        playbook_kept=kept,
        playbook_line=line if kept else "",
        trace_path=str(trace),
        browser=browsers,
        notes=[redact(note) for note in notes],
    )


def _prompt(
    role: str,
    task: str,
    *,
    playbook: str,
    round_no: int,
    extra: str = "",
    fail: str = "",
) -> str:
    return "\n".join(
        [
            f"ROLE={role}",
            f"ROUND={round_no}",
            f"TASK={task}",
            f"FAIL={fail}",
            f"EXTRA={extra}",
            "PLAYBOOK:",
            playbook.strip(),
        ]
    )


def _parse(raw: str) -> dict:
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _apply(repo: Path, role: str, files: object, before: dict[str, str]) -> list[str]:
    if not isinstance(files, list):
        return []
    written: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        rel = str(item.get("path") or "")
        safe = _safe_path(role, rel)
        if safe is None:
            continue
        target = repo / safe
        key = safe.as_posix()
        if key not in before:
            before[key] = target.read_text(encoding="utf-8") if target.is_file() else ""
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(item.get("content") or ""), encoding="utf-8")
        written.append(key)
    return written


def _safe_path(role: str, rel: str) -> Path | None:
    if not rel or rel.startswith("/") or rel.startswith("~"):
        return None
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts:
        return None
    posix = path.as_posix()
    if posix == "BRIEF.md" or posix == "claw.env" or posix.startswith(_BANNED_PREFIXES):
        return None
    if role == "ui" and not posix.startswith("product/ui/"):
        return None
    if role == "writer" and posix.startswith("product/ui/"):
        return None
    return path


def _diff(repo: Path, before: dict[str, str]) -> str:
    chunks: list[str] = []
    for rel, old in before.items():
        target = repo / rel
        new = target.read_text(encoding="utf-8") if target.is_file() else ""
        if old == new:
            continue
        chunks.append(f"--- {rel}\n+++ {rel}\n")
        chunks.append(_unified(old, new))
    return redact("".join(chunks))[:4000]


def _unified(old: str, new: str) -> str:
    import difflib

    lines = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        lineterm="",
        n=2,
    )
    return "\n".join(lines) + "\n"
