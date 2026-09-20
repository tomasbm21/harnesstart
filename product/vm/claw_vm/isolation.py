"""What the VM boundary actually isolates (honest; this nested host is special)."""

from __future__ import annotations

from .kvm import kvm_report, vcpu_known_good


def isolation_report(*, vmm: str, accel: str | None = None) -> dict[str, object]:
    kvm = kvm_report(probe_vcpu=False)
    hardware = bool(vcpu_known_good() and (vmm.startswith("firecracker") or accel == "kvm"))
    if vmm.startswith("firecracker"):
        boundary = (
            "Firecracker microVM on KVM: separate guest kernel, virtio-blk disk, "
            "minimal device model. Not a container, LXC, gVisor, or process jail."
        )
        isolated = [
            "Guest kernel and PID 1 (not the host's)",
            "Guest root filesystem (per-instance ext4; host trees not mounted)",
            "KVM EPT/VMX second-level address translation (when vCPU create works)",
            "No Docker/OCI runtime",
        ]
    else:
        kind = accel or "tcg"
        boundary = (
            f"QEMU VM ({kind}): separate guest kernel and virtio disk. "
            "Not a container, LXC, gVisor, or host process namespace."
        )
        isolated = [
            "Guest kernel and PID 1 (not the host's)",
            "Guest root filesystem (qcow2 overlay; host trees not mounted)",
            "QEMU user-net NAT (slirp): guest is not on a host bridge; "
            "set CLAW_VM_RESTRICT=1 to block guest-initiated sockets",
            "No Docker/OCI runtime",
        ]
        if kind == "kvm":
            isolated.insert(
                2,
                "KVM EPT/VMX second-level address translation",
            )
        else:
            isolated.insert(
                2,
                "TCG software VMM (this nested host cannot CREATE_VCPU; no EPT for L2)",
            )
    not_isolated = [
        "The VMM process still runs as a host process (Firecracker or QEMU)",
        "Hostfwd SSH is a deliberate hole from the host into guest:22",
        "Secrets in claw.env are not injected; do not copy them into the guest",
    ]
    if not hardware:
        not_isolated.append(
            "Hardware VMX/EPT for this L2 guest: nested KVM_CREATE_VCPU kernel-BUGs "
            "on Cursor Linux cloud (alloc_loaded_vmcs). Firecracker/QEMU-KVM/libkrun "
            "all need that ioctl. Default here is QEMU TCG until a host with working "
            "nested VMX is used (Lima claw-host / bare metal)."
        )
    return {
        "r2_vm_boundary": True,
        "r2_hardware_kvm": hardware,
        "vmm": vmm,
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
        "containers": False,
    }
