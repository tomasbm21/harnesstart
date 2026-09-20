"""Select and load VM computers. QEMU is the default; CLAW_VM_BACKEND env wins."""

from __future__ import annotations

import os

from .backends import SPECS, doctor_backend, live_start_for
from .computer import BackendComputer, Computer, FirecrackerComputer, QemuComputer
from .kvm import vcpu_known_good
from .names import (
    DEFAULT_BACKEND,
    KNOWN_BACKENDS,
    UnknownBackend,
    canonical_backend,
    normalize_backend,
)
from .paths import selected_path, vm_home


def selected_source() -> tuple[str, str]:
    """Return (backend_id, source) where source is env | file | default."""
    backend_env = (os.environ.get("CLAW_VM_BACKEND") or "").strip()
    resolved = canonical_backend(backend_env)
    if resolved:
        return resolved, "env"
    vmm_env = (os.environ.get("CLAW_VM_VMM") or "").strip()
    resolved = canonical_backend(vmm_env)
    if resolved:
        return resolved, "env"
    path = selected_path()
    if path.is_file():
        raw = path.read_text(encoding="utf-8").strip().splitlines()
        if raw:
            return normalize_backend(raw[0]), "file"
    return DEFAULT_BACKEND, "default"


def selected_id() -> str:
    return selected_source()[0]


def select(backend_id: str) -> str:
    resolved = normalize_backend(backend_id)
    home = vm_home()
    home.mkdir(parents=True, exist_ok=True)
    selected_path().write_text(resolved + "\n", encoding="utf-8")
    return resolved


def resolve_backend(requested: str | None = None) -> str:
    resolved = canonical_backend(requested)
    if resolved:
        return resolved
    if requested and requested.strip() and requested.strip().lower() not in {"auto", ""}:
        raise UnknownBackend(
            f"unknown backend {requested!r}. Choose one of: {', '.join(KNOWN_BACKENDS)}"
        )
    return selected_id()


def selected_computer() -> Computer:
    bid = selected_id()
    if bid == "firecracker":
        return FirecrackerComputer()
    if bid == "qemu":
        accel = "kvm" if vcpu_known_good() else "tcg"
        vmm = (os.environ.get("CLAW_VM_VMM") or "").lower()
        if vmm == "qemu-kvm":
            accel = "kvm"
        return QemuComputer(accel=accel)
    return BackendComputer(name=bid)


def list_backends() -> list[dict[str, object]]:
    current = selected_id()
    items = []
    for name in KNOWN_BACKENDS:
        report = doctor_backend(name)
        report["selected"] = name == current
        items.append(report)
    return items


def get_spec(backend_id: str):
    return SPECS[normalize_backend(backend_id)]


def live_start(backend_id: str | None = None):
    return live_start_for(backend_id or selected_id())
