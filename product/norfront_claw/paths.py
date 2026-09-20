"""Locate the harnesstart repo from the package or CLAW_REPO."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root(start: Path | None = None) -> Path:
    env = os.environ.get("CLAW_REPO")
    if env:
        return Path(env).expanduser().resolve()
    here = (start or Path(__file__).resolve()).parent
    for candidate in [here, *here.parents]:
        if (candidate / "BRIEF.md").is_file() and (candidate / "product").is_dir():
            return candidate
    return Path.cwd().resolve()


def product_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "product"


def xdg_data_home() -> Path:
    raw = os.environ.get("XDG_DATA_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".local" / "share"
