"""sudo / ACL helpers. Never print secrets."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

try:
    import pwd
except ImportError:  # Windows has no pwd module
    pwd = None  # type: ignore[assignment]


def have(cmd: str) -> bool:
    if shutil.which(cmd):
        return True
    name = Path(cmd).name
    for folder in ("/usr/sbin", "/sbin", "/usr/bin", "/bin"):
        candidate = Path(folder) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return True
    return False


def _euid() -> int | None:
    fn = getattr(os, "geteuid", None)
    if not callable(fn):
        return None
    try:
        return int(fn())
    except OSError:
        return None


def _uid() -> int | None:
    fn = getattr(os, "getuid", None)
    if not callable(fn):
        return None
    try:
        return int(fn())
    except OSError:
        return None


def can_sudo() -> bool:
    euid = _euid()
    if euid is None:
        return False
    if euid == 0:
        return True
    try:
        return subprocess.run(
            ["sudo", "-n", "true"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def username() -> str:
    uid = _uid()
    if pwd is not None and uid is not None:
        try:
            return pwd.getpwuid(uid).pw_name
        except KeyError:
            pass
    return os.environ.get("USER") or os.environ.get("USERNAME") or "user"


def run(
    argv: Sequence[str],
    *,
    privileged: bool = False,
    check: bool = True,
    capture: bool = False,
    timeout: float | None = None,
    cwd: str | os.PathLike[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = list(argv)
    if privileged and _euid() != 0:
        cmd = ["sudo", "-n", *cmd]
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture,
        timeout=timeout,
        cwd=cwd,
    )
