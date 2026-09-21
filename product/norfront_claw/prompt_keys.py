"""TTY boot prompts for missing keys. Never print values. Never put keys on argv."""

from __future__ import annotations

import getpass
import os
import re
import sys
from pathlib import Path

from .config import (
    SECRET_KEYS,
    Config,
    is_present,
    load_config,
    secret_is_set,
)

NO_PROMPT_ENV = "CLAW_NO_KEY_PROMPT"

# (name, optional): optional empty Enter skips without writing.
DEEPSEEK = "DEEPSEEK_API_KEY"
TYPESAFE = "TYPESAFE_API_KEY"

_SAFE_VALUE = re.compile(r"^[A-Za-z0-9_./+:@%-]+$")


def stdin_is_tty() -> bool:
    try:
        return bool(sys.stdin.isatty())
    except Exception:
        return False


def _stdio_can_prompt() -> bool:
    """Need a real terminal. Piped CI capture (stdout+stderr) must not hang."""
    try:
        out = bool(sys.stdout.isatty() or sys.stderr.isatty())
    except Exception:
        out = False
    return stdin_is_tty() and out


def prompt_disabled(*, no_prompt: bool = False) -> bool:
    if no_prompt:
        return True
    raw = (os.environ.get(NO_PROMPT_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def should_prompt(*, no_prompt: bool = False) -> bool:
    return (not prompt_disabled(no_prompt=no_prompt)) and _stdio_can_prompt()


def keys_for_command(command: str) -> tuple[tuple[str, bool], ...]:
    """Return (env_name, optional) pairs to prompt for this claw subcommand."""
    if command == "doctor":
        return ((DEEPSEEK, False), (TYPESAFE, True))
    if command == "run":
        return ((DEEPSEEK, False),)
    if command in {"choose", "browse"}:
        return ((TYPESAFE, False),)
    return ()


def claw_env_path(root: Path) -> Path:
    return root / "claw.env"


def format_assignment(name: str, value: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError("refusing to write a multi-line secret")
    if any(c in value for c in "\"'\\"):
        raise ValueError("refusing to write a secret that cannot round-trip")
    if _SAFE_VALUE.fullmatch(value):
        return f"{name}={value}"
    # Quoted so parse_env_file can strip matching quotes (it does not unescape).
    return f'{name}="{value}"'


def _line_sets_key(line: str, name: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return False
    return stripped.split("=", 1)[0].strip() == name


def upsert_claw_env(path: Path, name: str, value: str) -> None:
    """Append or replace NAME= in claw.env. Caller must not log value."""
    if name not in SECRET_KEYS:
        raise ValueError("refusing to write a key that is not in SECRET_KEYS")
    if not is_present(value):
        raise ValueError("refusing to write an empty secret")
    assignment = format_assignment(name, value) + "\n"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = existing.splitlines(keepends=True)
    replaced = False
    out: list[str] = []
    for line in lines:
        if _line_sets_key(line, name):
            out.append(assignment)
            replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and not "".join(out).endswith("\n"):
            out.append("\n")
        out.append(assignment)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(out), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _read_secret(prompt: str) -> str:
    return getpass.getpass(prompt, stream=sys.stderr)


def _prompt_one(name: str, *, optional: bool) -> str | None:
    if optional:
        label = (
            f"{name} for live Jev policy (hidden, saved to claw.env, Enter to skip): "
        )
    else:
        label = f"{name} (hidden, saved to claw.env): "
    try:
        raw = _read_secret(label)
    except EOFError:
        return None
    value = (raw or "").strip()
    if not value:
        return None
    if value == "__stored_in_hermes__":
        return None
    return value


def ensure_boot_keys(
    cfg: Config,
    *,
    command: str,
    no_prompt: bool = False,
) -> Config:
    """Prompt once per missing boot key on a TTY. Reload config if anything is set."""
    wanted = keys_for_command(command)
    if not wanted or not should_prompt(no_prompt=no_prompt):
        return cfg
    wrote = False
    env_path = claw_env_path(cfg.repo_root)
    for name, optional in wanted:
        if secret_is_set(name):
            continue
        value = _prompt_one(name, optional=optional)
        if not value:
            continue
        os.environ[name] = value
        try:
            upsert_claw_env(env_path, name, value)
            print(
                f"claw: saved {name} to {env_path.name} (value not printed)",
                file=sys.stderr,
            )
        except OSError as exc:
            print(
                f"claw: could not write {env_path.name} ({type(exc).__name__}); "
                "using this process only",
                file=sys.stderr,
            )
        wrote = True
    if not wrote:
        return cfg
    return load_config(cfg.repo_root)
