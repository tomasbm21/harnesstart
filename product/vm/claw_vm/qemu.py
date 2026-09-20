"""QEMU backend: KVM if vCPU creation works, else TCG. Still a VM, not a container."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from . import priv
from .kvm import kvm_openable, vcpu_known_good


def qemu_bin() -> str:
    exe = "qemu-system-x86_64"
    if not priv.have(exe):
        raise RuntimeError("qemu-system-x86_64 missing; run claw-vm fetch / install qemu-system-x86")
    return exe


def accel_args(*, force: str | None = None) -> tuple[str, list[str]]:
    """Return (accel_name, argv fragment)."""
    if force == "tcg":
        return "tcg", ["-accel", "tcg", "-cpu", "qemu64"]
    if force == "kvm":
        return "kvm", ["-accel", "kvm", "-cpu", "host"]
    if vcpu_known_good() and kvm_openable():
        return "kvm", ["-accel", "kvm", "-cpu", "host"]
    return "tcg", ["-accel", "tcg", "-cpu", "qemu64"]


def argv(
    *,
    disk: Path,
    seed_iso: Path | None,
    serial_log: Path,
    qemu_log: Path,
    pidfile: Path,
    ssh_port: int,
    mem_mib: int,
    accel_force: str | None = None,
    monitor_sock: Path | None = None,
) -> tuple[str, list[str]]:
    accel, accel_argv = accel_args(force=accel_force)
    restrict = os.environ.get("CLAW_VM_RESTRICT", "0") == "1"
    netdev = f"user,id=net0,hostfwd=tcp:127.0.0.1:{ssh_port}-:22"
    if restrict:
        netdev = f"user,id=net0,restrict=on,hostfwd=tcp:127.0.0.1:{ssh_port}-:22"
    cmd = [
        qemu_bin(),
        *accel_argv,
        "-machine",
        "q35",
        "-m",
        str(mem_mib),
        "-smp",
        "1",
        "-display",
        "none",
        "-boot",
        "order=c,menu=off",
        "-serial",
        f"file:{serial_log}",
        "-drive",
        f"file={disk},if=virtio,format=qcow2,cache=writethrough,discard=unmap",
        "-netdev",
        netdev,
        "-device",
        "virtio-net-pci,netdev=net0",
        "-pidfile",
        str(pidfile),
        "-D",
        str(qemu_log),
    ]
    if monitor_sock is not None:
        cmd.extend(
            ["-monitor", f"unix:{monitor_sock},server=on,wait=off"]
        )
    if seed_iso is not None:
        cmd.extend(
            [
                "-drive",
                f"file={seed_iso},if=virtio,format=raw,media=disk,read-only=on",
            ]
        )
    return accel, cmd


def start_qemu(cmd: list[str], *, log: Path) -> subprocess.Popen[bytes]:
    log.parent.mkdir(parents=True, exist_ok=True)
    log_f = log.open("ab")
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=log_f,
        stderr=log_f,
        start_new_session=True,
    )
    return proc


def overlay_disk(template: Path, dest: Path, *, size: str = "2G") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        return dest
    subprocess.run(
        [
            "qemu-img",
            "create",
            "-f",
            "qcow2",
            "-F",
            "qcow2",
            "-b",
            str(template.resolve()),
            str(dest),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(["qemu-img", "resize", str(dest), size], check=True, stdout=subprocess.DEVNULL)
    return dest


def monitor_quit(sock: Path) -> bool:
    import socket as sockmod

    try:
        s = sockmod.socket(sockmod.AF_UNIX, sockmod.SOCK_STREAM)
        s.settimeout(2)
        s.connect(str(sock))
        s.sendall(b"quit\n")
        s.close()
        return True
    except OSError:
        return False


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def stop_pid(pid: int, *, timeout: float = 10.0) -> None:
    if not pid_alive(pid):
        return
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pid_alive(pid):
            return
        time.sleep(0.1)
    if pid_alive(pid):
        os.kill(pid, signal.SIGKILL)
