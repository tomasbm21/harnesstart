"""Linux-cloud VM computer for Norfront Claw (BRIEF R2).

Hardware isolation is a VM boundary, not a container. QEMU is the default
computer. Firecracker on KVM is selectable when nested vCPU creation works.
Optional computers: Celesto, E2B runtime, AgentENV, microsandbox, libkrun.

The claw CLI can call this later without owning this tree:

    from claw_vm import ClawVM, start, stop, exec_in, doctor, fetch, default_computer
    from claw_vm import list_backends, select, selected_id
"""

from .backends import StartSkipped
from .computer import BackendComputer, FirecrackerComputer, QemuComputer, default_computer
from .instance import ClawVM, ExecResult, destroy, exec_in, start, status, stop
from .isolation import isolation_report
from .kvm import kvm_report
from .names import DEFAULT_BACKEND, KNOWN_BACKENDS, UnknownBackend
from .paths import vm_home
from .registry import list_backends, select, selected_id, selected_source

__version__ = "0.2.0"

__all__ = [
    "BackendComputer",
    "ClawVM",
    "DEFAULT_BACKEND",
    "ExecResult",
    "FirecrackerComputer",
    "KNOWN_BACKENDS",
    "QemuComputer",
    "StartSkipped",
    "UnknownBackend",
    "default_computer",
    "destroy",
    "doctor",
    "exec_in",
    "fetch",
    "isolation_report",
    "kvm_report",
    "list_backends",
    "select",
    "selected_id",
    "selected_source",
    "start",
    "status",
    "stop",
    "vm_home",
    "__version__",
]


def doctor() -> dict[str, object]:
    from .cli import doctor_payload

    return doctor_payload()


def fetch(*, image: str | None = None, vmm: str | None = None) -> dict[str, object]:
    from .assets import fetch_assets

    return fetch_assets(image=image, vmm=vmm)
