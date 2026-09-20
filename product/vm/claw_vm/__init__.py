"""Linux-cloud VM computer for Norfront Claw (BRIEF R2).

Hardware isolation is a VM boundary, not a container. The preferred VMM is
Firecracker on KVM. This package also ships QEMU (KVM or TCG) so a guest can
still boot when nested KVM vCPU creation is broken.

The claw CLI can call this later without owning this tree:

    from claw_vm import ClawVM, start, stop, exec_in, doctor, fetch, default_computer
"""

from .computer import FirecrackerComputer, QemuComputer, default_computer
from .instance import ClawVM, ExecResult, destroy, exec_in, start, status, stop
from .isolation import isolation_report
from .kvm import kvm_report
from .paths import vm_home

__version__ = "0.1.0"

__all__ = [
    "ClawVM",
    "ExecResult",
    "FirecrackerComputer",
    "QemuComputer",
    "default_computer",
    "destroy",
    "doctor",
    "exec_in",
    "fetch",
    "isolation_report",
    "kvm_report",
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
