"""XDG paths for the VM computer. Runtime state stays out of the git tree."""

from __future__ import annotations

import os
import re
from pathlib import Path

NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


def repo_root() -> Path:
    env = os.environ.get("CLAW_REPO")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[3]


def vm_home() -> Path:
    env = os.environ.get("CLAW_VM_HOME")
    if env:
        return Path(env).resolve()
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return (base / "norfront-claw" / "vm").resolve()


def assets_dir() -> Path:
    return vm_home() / "assets"


def instances_dir() -> Path:
    return vm_home() / "instances"


def instance_dir(name: str) -> Path:
    check_name(name)
    return instances_dir() / name


def check_name(name: str) -> str:
    if not NAME_RE.match(name):
        raise ValueError(
            f"invalid VM name {name!r}: use a lowercase letter, then [a-z0-9-] (max 32)"
        )
    return name
