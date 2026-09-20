"""Host probes that never CREATE_VCPU and never print secrets."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import priv
from .kvm import kvm_present, vcpu_known_good
from .paths import vm_home


def docker_present() -> bool:
    return bool(shutil.which("docker") or shutil.which("podman"))


def qemu_present() -> bool:
    return priv.have("qemu-system-x86_64")


def local_bin() -> Path:
    return Path.home() / ".local" / "bin"


def extra_bin_dirs() -> list[Path]:
    dirs = [local_bin(), vm_home() / "bin", vm_home() / "venv" / "bin"]
    env = os.environ.get("CLAW_VM_BIN")
    if env:
        dirs.insert(0, Path(env).expanduser())
    return dirs


def which_binary(configured: str, names: tuple[str, ...]) -> str | None:
    candidates: list[str] = []
    if configured:
        candidates.append(configured)
    for name in names:
        if name and name not in candidates:
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
        for folder in extra_bin_dirs():
            candidate = folder / raw
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return None


def find_library(names: tuple[str, ...]) -> str | None:
    search_dirs = [
        Path("/usr/lib"),
        Path("/usr/lib64"),
        Path("/usr/local/lib"),
        Path("/usr/lib/x86_64-linux-gnu"),
        Path("/lib/x86_64-linux-gnu"),
        Path("/usr/local/lib64"),
        vm_home() / "lib",
    ]
    for name in names:
        for folder in search_dirs:
            candidate = folder / name
            if candidate.is_file():
                return str(candidate)
        env = os.environ.get("LD_LIBRARY_PATH") or ""
        for part in env.split(os.pathsep):
            if not part:
                continue
            candidate = Path(part) / name
            if candidate.is_file():
                return str(candidate)
    try:
        proc = subprocess.run(
            ["ldconfig", "-p"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        proc = None
    blob = (proc.stdout or "") if proc else ""
    for name in names:
        stem = name.split(".so")[0]
        if stem and stem in blob:
            for line in blob.splitlines():
                if stem in line and "=>" in line:
                    path = line.split("=>", 1)[1].strip()
                    if path and Path(path).is_file():
                        return path
    return None


def working_kvm() -> bool:
    """True only if a prior CREATE_VCPU probe cache says ok. Never probes."""
    return vcpu_known_good()


def kvm_live_ok() -> bool:
    """Live KVM guests need a working vCPU. Missing /dev/kvm is also a skip."""
    if not kvm_present():
        return False
    return working_kvm()
