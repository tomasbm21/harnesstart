"""Computer protocol the claw CLI can load later: from claw_vm import default_computer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .isolation import isolation_report
from .kvm import kvm_report, vcpu_known_good


@runtime_checkable
class Computer(Protocol):
    name: str
    r2_isolated: bool

    def doctor(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class FirecrackerComputer:
    name: str = "firecracker"
    r2_isolated: bool = True

    def doctor(self) -> dict[str, object]:
        kvm = kvm_report(probe_vcpu=False)
        return {
            "name": self.name,
            "r2_isolated": self.r2_isolated,
            "vmm": "firecracker",
            "needs_kvm_vcpu": True,
            "kvm_vcpu_ok": vcpu_known_good(),
            "kvm": kvm,
            "isolation": isolation_report(vmm="firecracker", accel="kvm"),
        }


@dataclass(frozen=True)
class QemuComputer:
    name: str = "qemu"
    r2_isolated: bool = True
    accel: str = "tcg"

    def doctor(self) -> dict[str, object]:
        return {
            "name": self.name,
            "r2_isolated": self.r2_isolated,
            "vmm": "qemu",
            "accel": self.accel,
            "kvm": kvm_report(probe_vcpu=False),
            "isolation": isolation_report(vmm="qemu", accel=self.accel),
        }


def default_computer() -> Computer:
    vmm = (os.environ.get("CLAW_VM_VMM") or "auto").lower()
    if vmm == "firecracker" or (vmm == "auto" and vcpu_known_good()):
        return FirecrackerComputer()
    accel = "kvm" if vcpu_known_good() else "tcg"
    if vmm == "qemu-kvm":
        accel = "kvm"
    return QemuComputer(accel=accel)
