"""What the VM boundary actually isolates (honest; this nested host is special)."""

from __future__ import annotations

from .kvm import kvm_report, vcpu_known_good
from .names import canonical_backend

_KVM_FAMILIES = frozenset(
    {"firecracker", "celesto", "e2b", "agentenv", "microsandbox", "libkrun"}
)


def isolation_report(*, vmm: str, accel: str | None = None) -> dict[str, object]:
    kvm = kvm_report(probe_vcpu=False)
    backend = canonical_backend(vmm) or vmm
    hardware = bool(vcpu_known_good() and (backend in _KVM_FAMILIES or accel == "kvm"))
    boundary, isolated, extra_not = _copy(backend, accel)
    not_isolated = [
        "The VMM process still runs as a host process",
        "A host control channel into the guest (SSH/vsock/SDK) is a deliberate hole",
        "Secrets in claw.env are not injected; do not copy them into the guest",
        *extra_not,
    ]
    if not hardware:
        not_isolated.append(
            "Hardware VMX/EPT for this L2 guest: nested KVM_CREATE_VCPU kernel-BUGs "
            "on Cursor Linux cloud (alloc_loaded_vmcs). Firecracker/QEMU-KVM/libkrun "
            "all need that ioctl. Default here is QEMU TCG until a host with working "
            "nested VMX is used (Lima claw-host / bare metal)."
        )
    containers = False
    return {
        "r2_vm_boundary": True,
        "r2_hardware_kvm": hardware,
        "vmm": backend,
        "accel": accel,
        "boundary": boundary,
        "isolated": isolated,
        "not_isolated": not_isolated,
        "kvm": {
            "present": kvm["present"],
            "openable": kvm["openable"],
            "nested": kvm["nested"],
            "vcpu_ok": (kvm["vcpu"] or {}).get("ok") if isinstance(kvm.get("vcpu"), dict) else None,
        },
        "containers": containers,
    }


def _copy(backend: str, accel: str | None) -> tuple[str, list[str], list[str]]:
    if backend == "firecracker":
        return (
            "Firecracker microVM on KVM: separate guest kernel, virtio-blk disk, "
            "minimal device model. Not a container, LXC, gVisor, or process jail.",
            [
                "Guest kernel and PID 1 (not the host's)",
                "Guest root filesystem (per-instance ext4; host trees not mounted)",
                "KVM EPT/VMX second-level address translation (when vCPU create works)",
                "No Docker/OCI runtime",
            ],
            [],
        )
    if backend == "celesto":
        return (
            "Celesto (SmolVM) Firecracker microVM on Linux: persistent agent computer. "
            "Not a container. Optional Celesto Cloud is not required and is not used.",
            [
                "Guest kernel (Firecracker on Linux)",
                "Persistent sandbox disk / snapshots",
                "KVM isolation when CREATE_VCPU works",
                "Browser/desktop templates stay inside the guest",
            ],
            [
                "Linux desktop template's first image build may want Docker — that path is not started here",
                "Do not set provider=cloud (hosted CP; BRIEF R4)",
            ],
        )
    if backend == "e2b":
        return (
            "E2B Runtime Embed: one Firecracker microVM per sandbox (pause/resume/fork). "
            "Isolation is the microVM, not Docker. E2B Cloud is not required.",
            [
                "Guest kernel via Firecracker",
                "Per-sandbox overlay disk and snapshot/resume",
                "nftables egress on the node when Embed is running",
            ],
            [
                "Embed packaging uses Docker Compose on the host to run the stack — skip live start without Docker",
                "Do not require E2B Cloud API keys",
            ],
        )
    if backend == "agentenv":
        return (
            "AgentENV self-hosted Firecracker environments with an E2B-compatible API (MIT). "
            "Not a desktop product.",
            [
                "Guest kernel via Firecracker",
                "Snapshot/pause/resume on the local server",
                "API talks to your machines, not a required hosted CP",
            ],
            [
                "The local server API key file is never read or printed by claw-vm",
            ],
        )
    if backend == "microsandbox":
        return (
            "microsandbox libkrun microVMs on KVM Linux. OCI images boot inside a VM, "
            "not as a host Docker sandbox. Local-first; no required hosted CP.",
            [
                "libkrun VMM + guest kernel",
                "KVM isolation when CREATE_VCPU works",
                "Secrets are designed not to enter the guest",
            ],
            [],
        )
    if backend == "libkrun":
        return (
            "libkrun embeddable VMM (KVM on Linux). Hardware VM isolation primitive "
            "used by microsandbox and OpenShell's VM driver. Not an agent loop.",
            [
                "KVM guest (when vCPU create works)",
                "Minimal emulated device model",
                "No Docker/OCI runtime required by the library itself",
            ],
            [
                "No generic computer CLI — pair with microsandbox or OpenShell VM driver to launch a guest",
            ],
        )
    kind = accel or "tcg"
    isolated = [
        "Guest kernel and PID 1 (not the host's)",
        "Guest root filesystem (qcow2 overlay; host trees not mounted)",
        "QEMU user-net NAT (slirp): guest is not on a host bridge; "
        "set CLAW_VM_RESTRICT=1 to block guest-initiated sockets",
        "No Docker/OCI runtime",
    ]
    if kind == "kvm":
        isolated.insert(2, "KVM EPT/VMX second-level address translation")
    else:
        isolated.insert(
            2,
            "TCG software VMM (this nested host cannot CREATE_VCPU; no EPT for L2)",
        )
    return (
        f"QEMU VM ({kind}): separate guest kernel and virtio disk. "
        "Not a container, LXC, gVisor, or host process namespace.",
        isolated,
        [],
    )
