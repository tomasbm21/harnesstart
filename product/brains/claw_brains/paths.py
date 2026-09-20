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


def nvm_dir() -> Path:
    raw = os.environ.get("NVM_DIR")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".nvm"


def nvm_bin_dirs() -> list[Path]:
    """Newest-first nvm node bin dirs (OpenClaw npm -g lands here)."""
    versions = nvm_dir() / "versions" / "node"
    if not versions.is_dir():
        return []
    dirs = [p for p in versions.glob("*/bin") if p.is_dir()]
    dirs.sort(key=lambda p: p.parent.name, reverse=True)
    return dirs
