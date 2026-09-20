"""Agent computer. v0 is the Linux host process — R2 VM isolation is stubbed."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Computer(Protocol):
    """Hardware-isolated agent computer (BRIEF R2). Implement with Firecracker/libkrun later."""

    name: str
    r2_isolated: bool

    def doctor(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class HostComputer:
    """The cloud Linux user account. Not a VM boundary. /dev/kvm is unused."""

    name: str = "host-linux"
    r2_isolated: bool = False
    kvm_path: Path = Path("/dev/kvm")

    def kvm_present(self) -> bool:
        return self.kvm_path.exists()

    def doctor(self) -> dict[str, object]:
        return {
            "name": self.name,
            "r2_isolated": self.r2_isolated,
            "os": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "kvm": self.kvm_present(),
            "uid": os.getuid() if hasattr(os, "getuid") else None,
            "stub": "R2: wrap Prime Agent in a Firecracker/libkrun guest; this is the host.",
        }


def default_computer() -> HostComputer:
    return HostComputer()
