"""sudo / ACL helpers. Never print secrets."""

from __future__ import annotations

import os
import pwd
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path


def have(cmd: str) -> bool:
    if shutil.which(cmd):
        return True
    name = Path(cmd).name
    for folder in ("/usr/sbin", "/sbin", "/usr/bin", "/bin"):
        candidate = Path(folder) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return True
    return False


def can_sudo() -> bool:
    if os.geteuid() == 0:
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
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except KeyError:
        return os.environ.get("USER", "ubuntu")


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
    if privileged and os.geteuid() != 0:
        cmd = ["sudo", "-n", *cmd]
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture,
        timeout=timeout,
        cwd=cwd,
    )
