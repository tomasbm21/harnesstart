"""Optional VM computers. QEMU stays default. Skip live start without KVM/Docker."""

from __future__ import annotations

from dataclasses import dataclass, field

from .host import (
    docker_present,
    find_library,
    kvm_live_ok,
    qemu_present,
    which_binary,
)
from .isolation import isolation_report
from .kvm import kvm_present, kvm_report, vcpu_known_good
from .names import BUILTIN_VMMS, KNOWN_BACKENDS, normalize_backend
from .secrets import presence_label, refuse_secret_flags

SKIP_NO_KVM = "skipped-no-kvm"
SKIP_NO_DOCKER = "skipped-no-docker"
SKIP_NOT_INSTALLED = "skipped-not-installed"
SKIP_NO_CLI = "skipped-no-cli"
READY = "ready"


class StartSkipped(RuntimeError):
    """Live start was not attempted (missing KVM, Docker, or binary)."""

    def __init__(self, backend: str, reason: str, detail: str):
        self.backend = backend
        self.reason = reason
        self.detail = detail
        super().__init__(detail)

    def payload(self) -> dict[str, object]:
        return {
            "ok": False,
            "skipped": True,
            "backend": self.backend,
            "reason": self.reason,
            "detail": self.detail,
            "started": False,
        }


@dataclass(frozen=True)
class BackendSpec:
    id: str
    name: str
    license: str
    repo: str
    vmm: str
    needs_kvm: bool
    needs_docker: bool
    binaries: tuple[str, ...] = ()
    libs: tuple[str, ...] = ()
    env_bin: str = ""
    hosted_keys: tuple[str, ...] = ()
    start_hint: str = ""
    notes: str = ""


SPECS: dict[str, BackendSpec] = {
    "qemu": BackendSpec(
        id="qemu",
        name="QEMU",
        license="GPL-2.0",
        repo="https://gitlab.com/qemu-project/qemu",
        vmm="qemu",
        needs_kvm=False,
        needs_docker=False,
        binaries=("qemu-system-x86_64",),
        start_hint="./product/vm/claw-vm fetch && ./product/vm/claw-vm start agent",
        notes="Default computer. TCG works without KVM; still a VM boundary.",
    ),
    "firecracker": BackendSpec(
        id="firecracker",
        name="Firecracker",
        license="Apache-2.0",
        repo="https://github.com/firecracker-microvm/firecracker",
        vmm="firecracker",
        needs_kvm=True,
        needs_docker=False,
        binaries=("firecracker",),
        start_hint="./product/vm/claw-vm fetch --vmm firecracker && ./product/vm/claw-vm start agent --backend firecracker",
        notes="Preferred VMM when nested KVM vCPU creation works. Not the default.",
    ),
    "celesto": BackendSpec(
        id="celesto",
        name="Celesto",
        license="Apache-2.0",
        repo="https://github.com/CelestoAI/celesto",
        vmm="firecracker",
        needs_kvm=True,
        needs_docker=False,
        binaries=("celesto",),
        env_bin="CLAW_VM_CELESTO_BIN",
        hosted_keys=("CELESTO_API_KEY",),
        start_hint="celesto sandbox create --name agent  # local Firecracker; never provider=cloud",
        notes=(
            "Linux computers are Firecracker microVMs. Optional Celesto Cloud is not used (R4). "
            "The Linux desktop template's first image build wants Docker; that path is not started here."
        ),
    ),
    "e2b": BackendSpec(
        id="e2b",
        name="E2B Runtime",
        license="Apache-2.0",
        repo="https://github.com/e2b-dev/runtime",
        vmm="firecracker",
        needs_kvm=True,
        needs_docker=True,
        binaries=("e2b",),
        env_bin="CLAW_VM_E2B_BIN",
        hosted_keys=("E2B_API_KEY", "E2B_ACCESS_TOKEN"),
        start_hint="E2B Embed: docker compose up in embed/ on a KVM host. Not E2B Cloud.",
        notes=(
            "Isolation is Firecracker, not Docker. Embed packaging needs Docker Compose + KVM. "
            "Do not require E2B Cloud."
        ),
    ),
    "agentenv": BackendSpec(
        id="agentenv",
        name="AgentENV",
        license="MIT",
        repo="https://github.com/kvcache-ai/AgentENV",
        vmm="firecracker",
        needs_kvm=True,
        needs_docker=False,
        binaries=("aenv",),
        env_bin="CLAW_VM_AENV_BIN",
        hosted_keys=("AENV_API_KEY", "AGENTENV_API_KEY"),
        start_hint="aenv start <template> --detach  # local server; never print the API key file",
        notes="Self-host Firecracker with an E2B-compatible API. Server API key file is never read.",
    ),
    "microsandbox": BackendSpec(
        id="microsandbox",
        name="microsandbox",
        license="Apache-2.0",
        repo="https://github.com/superradcompany/microsandbox",
        vmm="libkrun",
        needs_kvm=True,
        needs_docker=False,
        binaries=("msb", "microsandbox"),
        env_bin="CLAW_VM_MSB_BIN",
        start_hint="msb create --name agent ubuntu  # libkrun microVM; needs KVM",
        notes="Local-first libkrun microVMs. OCI images inside a VM, not a host Docker sandbox.",
    ),
    "libkrun": BackendSpec(
        id="libkrun",
        name="libkrun",
        license="Apache-2.0",
        repo="https://github.com/libkrun/libkrun",
        vmm="libkrun",
        needs_kvm=True,
        needs_docker=False,
        libs=("libkrun.so.1", "libkrun.so", "libkrun.so.2"),
        start_hint="libkrun is a VMM library; launch via microsandbox or OpenShell's VM driver.",
        notes="Isolation primitive, not an agent. Used by microsandbox and OpenShell compute-driver-vm.",
    ),
}


@dataclass
class LiveStart:
    reason: str
    detail: str
    skip_reasons: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.reason == READY


def _configured_bin(spec: BackendSpec) -> str:
    if not spec.env_bin:
        return ""
    import os

    return (os.environ.get(spec.env_bin) or "").strip()


def locate(spec: BackendSpec) -> str | None:
    if spec.id == "qemu":
        if qemu_present():
            return which_binary("", spec.binaries) or "qemu-system-x86_64"
        return None
    if spec.libs:
        found_lib = find_library(spec.libs)
        if found_lib:
            return found_lib
    if spec.binaries:
        return which_binary(_configured_bin(spec), spec.binaries)
    return None


def live_start_for(backend_id: str) -> LiveStart:
    spec = SPECS[normalize_backend(backend_id)]
    reasons: list[str] = []
    details: list[str] = []
    if spec.needs_kvm and not kvm_live_ok():
        reasons.append(SKIP_NO_KVM)
        if not kvm_present():
            details.append("/dev/kvm missing")
        else:
            details.append(
                "working KVM vCPU not confirmed; not probing CREATE_VCPU "
                "(nested hosts kernel-BUG). Firecracker/libkrun need that ioctl."
            )
    if spec.needs_docker and not docker_present():
        reasons.append(SKIP_NO_DOCKER)
        details.append("Docker/Podman missing (E2B Embed packaging, not the guest isolation)")
    located = locate(spec)
    if spec.id == "libkrun":
        if not located:
            reasons.append(SKIP_NOT_INSTALLED)
            details.append("libkrun.so not on this host")
        elif SKIP_NO_KVM not in reasons:
            reasons.append(SKIP_NO_CLI)
            details.append(spec.start_hint)
    elif spec.binaries and not located:
        reasons.append(SKIP_NOT_INSTALLED)
        if spec.id == "qemu":
            details.append("qemu-system-x86_64 missing")
        else:
            details.append(f"{spec.binaries[0]} not on PATH")
    if not reasons:
        return LiveStart(reason=READY, detail="live start allowed", skip_reasons=[])
    return LiveStart(
        reason=reasons[0],
        detail="; ".join(details) if details else reasons[0],
        skip_reasons=reasons,
    )


def doctor_backend(backend_id: str) -> dict[str, object]:
    spec = SPECS[normalize_backend(backend_id)]
    located = locate(spec)
    live = live_start_for(spec.id)
    accel = None
    if spec.id == "qemu":
        accel = "kvm" if vcpu_known_good() else "tcg"
    elif spec.needs_kvm:
        accel = "kvm"
    iso = isolation_report(vmm=spec.id, accel=accel)
    keys = {name: presence_label(name) for name in spec.hosted_keys}
    return {
        "name": spec.id,
        "display": spec.name,
        "r2_isolated": True,
        "vmm": spec.vmm,
        "accel": accel,
        "present": located is not None,
        "binary": located,
        "live_start": live.reason,
        "skip_reasons": live.skip_reasons,
        "live_detail": live.detail,
        "needs_kvm": spec.needs_kvm,
        "needs_kvm_vcpu": spec.needs_kvm,
        "needs_docker": spec.needs_docker,
        "kvm_vcpu_ok": vcpu_known_good(),
        "kvm": kvm_report(probe_vcpu=False),
        "docker": docker_present(),
        "isolation": iso,
        "license": spec.license,
        "repo": spec.repo,
        "notes": spec.notes,
        "start_hint": spec.start_hint,
        "keys": keys,
        "hosted_control_plane": False,
    }


def list_backend_doctors() -> list[dict[str, object]]:
    return [doctor_backend(name) for name in KNOWN_BACKENDS]


def start_backend(backend_id: str, name: str = "agent") -> dict[str, object]:
    """Start an optional computer, or skip without touching KVM/Docker."""
    spec = SPECS[normalize_backend(backend_id)]
    live = live_start_for(spec.id)
    if not live.ready:
        raise StartSkipped(spec.id, live.reason, live.detail)
    if spec.id in BUILTIN_VMMS:
        raise StartSkipped(
            spec.id,
            SKIP_NO_CLI,
            "qemu/firecracker start goes through claw_vm.instance, not start_backend",
        )
    located = locate(spec)
    if spec.id == "celesto":
        argv = refuse_secret_flags([located or "celesto", "sandbox", "create", "--name", name])
        return _run_optional(spec.id, argv)
    if spec.id == "microsandbox":
        argv = refuse_secret_flags([located or "msb", "create", "--name", name, "ubuntu"])
        return _run_optional(spec.id, argv)
    if spec.id == "agentenv":
        argv = refuse_secret_flags([located or "aenv", "start", name, "--detach"])
        return _run_optional(spec.id, argv)
    if spec.id == "e2b":
        # Ready means Docker + KVM + binary. Still do not talk to E2B Cloud.
        argv = refuse_secret_flags([located or "e2b", "sandbox", "spawn"])
        return _run_optional(spec.id, argv)
    raise StartSkipped(spec.id, SKIP_NO_CLI, spec.start_hint)


def _run_optional(backend_id: str, argv: list[str]) -> dict[str, object]:
    import subprocess

    refuse_secret_flags(argv)
    try:
        proc = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"{backend_id} start failed: {type(exc).__name__}") from exc
    from .secrets import redact

    if proc.returncode != 0:
        raise RuntimeError(
            f"{backend_id} start exit {proc.returncode}: "
            f"{redact((proc.stderr or proc.stdout or '')[-400:])}"
        )
    return {
        "ok": True,
        "skipped": False,
        "backend": backend_id,
        "started": True,
        "argv": argv,
        "detail": redact((proc.stdout or "").strip()[:400]),
    }
