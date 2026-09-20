"""Brain protocol. Live turns never put API keys on argv."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from .config import Config, presence_label
from .paths import local_bin

FORBIDDEN_FLAGS = frozenset(
    {
        "--api-key",
        "--apikey",
        "--llm-api-key",
        "--openai-api-key",
        "--deepseek-api-key",
    }
)


class BrainError(RuntimeError):
    pass


class MissingApiKey(BrainError):
    pass


class UnknownBrain(BrainError):
    pass


@dataclass(frozen=True)
class BrainSpec:
    id: str
    name: str
    role: str
    license: str
    repo: str
    binary_names: tuple[str, ...]
    install_url: str = ""
    isolation: str = (
        "Host process. Pair with product/vm for BRIEF R2. This is a brain, not a computer."
    )


@dataclass
class Check:
    id: str
    ok: bool
    detail: str
    warning: bool = False

    def asdict(self) -> dict:
        return asdict(self)


@dataclass
class BrainResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    argv: tuple[str, ...] = ()
    stubbed: bool = False
    reason: str = ""


@dataclass
class BrainDoctor:
    id: str
    name: str
    role: str
    present: bool
    version: str | None
    binary: str | None
    keys: dict[str, str]
    live_turn: str
    isolation: str
    checks: list[Check] = field(default_factory=list)
    stubbed: list[str] = field(default_factory=list)
    install_hint: str = ""
    license: str = ""
    repo: str = ""

    def asdict(self) -> dict:
        payload = asdict(self)
        return payload


class Brain(Protocol):
    spec: BrainSpec

    def which(self) -> str | None: ...
    def version(self) -> str | None: ...
    def doctor(self) -> BrainDoctor: ...
    def print_argv(self, prompt: str) -> list[str]: ...
    def run(self, prompt: str, *, timeout: int = 180) -> BrainResult: ...
    def install(self, *, timeout: int = 300) -> BrainResult: ...


def refuse_secret_flags(argv: list[str]) -> list[str]:
    lowered = [a.lower() for a in argv]
    for flag in FORBIDDEN_FLAGS:
        if flag in lowered:
            raise BrainError("internal error: refusing to put an API key flag on argv")
    joined = " ".join(argv)
    if "--api-key" in joined.lower():
        raise BrainError("internal error: refusing to put --api-key on argv")
    return argv


def which_binary(configured: str, names: tuple[str, ...]) -> str | None:
    candidates: list[str] = []
    if configured:
        candidates.append(configured)
    for name in names:
        if name not in candidates:
            candidates.append(name)
    for raw in candidates:
        if os.path.sep in raw or raw.startswith("~"):
            path = Path(raw).expanduser()
            if path.exists():
                return str(path)
            continue
        found = shutil.which(raw)
        if found:
            return found
        home = local_bin() / raw
        if home.exists():
            return str(home)
    return None


def probe_version(binary: str | None, args: tuple[str, ...] = ("--version",)) -> str | None:
    if not binary:
        return None
    try:
        proc = subprocess.run(
            [binary, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
            env=_child_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (proc.stdout or proc.stderr or "").strip()
    if not text:
        return None
    return text.splitlines()[0][:200]


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    local = str(local_bin())
    env["PATH"] = local + os.pathsep + env.get("PATH", "")
    return env


def run_argv(
    argv: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 180,
    extra_env: dict[str, str] | None = None,
) -> BrainResult:
    refuse_secret_flags(argv)
    env = _child_env()
    if extra_env:
        env.update(extra_env)
    try:
        proc = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(cwd) if cwd else None,
        )
    except subprocess.TimeoutExpired as exc:
        return BrainResult(
            ok=False,
            returncode=124,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=((exc.stderr or "") if isinstance(exc.stderr, str) else "") or "timeout",
            argv=tuple(argv),
        )
    except OSError as exc:
        return BrainResult(
            ok=False,
            returncode=1,
            stdout="",
            stderr=str(exc),
            argv=tuple(argv),
        )
    return BrainResult(
        ok=proc.returncode == 0,
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        argv=tuple(argv),
    )


def missing_key_stub(brain_id: str) -> BrainResult:
    return BrainResult(
        ok=False,
        returncode=2,
        stdout="",
        stderr=(
            f"{brain_id}: live model turn stubbed — DEEPSEEK_API_KEY is missing. "
            "Put it in claw.env locally (not in chat), then re-run."
        ),
        stubbed=True,
        reason="missing-key",
    )


def not_installed_stub(brain_id: str, hint: str) -> BrainResult:
    return BrainResult(
        ok=False,
        returncode=1,
        stdout="",
        stderr=f"{brain_id} is not on PATH. {hint}",
        stubbed=True,
        reason="not-installed",
    )


def key_status(cfg: Config, names: tuple[str, ...]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in names:
        if name == "DEEPSEEK_API_KEY":
            out[name] = presence_label(cfg.deepseek_key)
        elif name == "OPENAI_API_KEY":
            out[name] = presence_label(cfg.openai_key)
        elif name == "LLM_API_KEY":
            out[name] = presence_label(cfg.llm_api_key)
        else:
            from .config import secret_is_set

            out[name] = presence_label(secret_is_set(name))
    return out


def live_turn_state(*, present: bool, has_key: bool) -> str:
    if not present:
        return "not-installed"
    if not has_key:
        return "stubbed-no-key"
    return "ready"


def ensure_workspace(cfg: Config) -> Path:
    cfg.workspace.mkdir(parents=True, exist_ok=True)
    return cfg.workspace
