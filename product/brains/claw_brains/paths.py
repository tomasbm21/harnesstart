"""XDG paths. Never the harness git tree for agent cwd."""

from __future__ import annotations

import os
from pathlib import Path


def xdg_data_home() -> Path:
    raw = os.environ.get("XDG_DATA_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".local" / "share"


def repo_root() -> Path:
    env = os.environ.get("CLAW_REPO")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "BRIEF.md").is_file() and (parent / "product").is_dir():
            return parent
    return Path.cwd().resolve()


def product_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "product"


def brains_home() -> Path:
    override = os.environ.get("CLAW_BRAINS_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return xdg_data_home() / "norfront-claw" / "brains"


def selected_path() -> Path:
    return brains_home() / "selected"


def local_bin() -> Path:
    return Path.home() / ".local" / "bin"
