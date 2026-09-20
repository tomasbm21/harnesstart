"""Computer protocol the claw CLI can load later: from claw_vm import default_computer."""

from __future__ import annotations

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
        from .backends import doctor_backend

        return doctor_backend("firecracker")


@dataclass(frozen=True)
class QemuComputer:
    name: str = "qemu"
    r2_isolated: bool = True
    accel: str = "tcg"

    def doctor(self) -> dict[str, object]:
        from .backends import doctor_backend

        payload = doctor_backend("qemu")
        payload["accel"] = self.accel
        payload["isolation"] = isolation_report(vmm="qemu", accel=self.accel)
        payload["kvm"] = kvm_report(probe_vcpu=False)
        payload["kvm_vcpu_ok"] = vcpu_known_good()
        return payload


@dataclass(frozen=True)
class BackendComputer:
    """Optional computer (Celesto / E2B / AgentENV / microsandbox / libkrun)."""

    name: str
    r2_isolated: bool = True

    def doctor(self) -> dict[str, object]:
        from .backends import doctor_backend

        return doctor_backend(self.name)


def default_computer() -> Computer:
    from .registry import selected_computer

    return selected_computer()
