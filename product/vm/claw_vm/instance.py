"""Start / stop / exec a named VM. Persistent disk per instance."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .assets import (
    IMAGES,
    Image,
    build_fc_ext4,
    default_image_id,
    ensure_ssh_key,
    fc_ext4_template,
    fetch_assets,
    fetch_qemu_image,
    kernel_path,
    ssh_key_path,
    ssh_pub_path,
)
from .firecracker import (
    copy_rootfs,
    firecracker_config,
    guest_ip,
    guest_mac,
    host_ip,
    setup_tap,
    slot_from_name,
    start_firecracker,
    tap_name,
    teardown_tap,
    write_config,
)
from .backends import StartSkipped, live_start_for, start_backend
from .isolation import isolation_report
from .kvm import vcpu_known_good
from .names import BUILTIN_VMMS
from .paths import check_name, instance_dir, instances_dir
from .registry import resolve_backend
from .qemu import (
    argv as qemu_argv,
    monitor_quit,
    overlay_disk,
    pid_alive,
    start_qemu,
    stop_pid,
)
from .seed import write_cidata_iso

SSH_OPTS = [
    "-o",
    "BatchMode=yes",
    "-o",
    "StrictHostKeyChecking=no",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "GlobalKnownHostsFile=/dev/null",
    "-o",
    "IdentitiesOnly=yes",
    "-o",
    "ConnectTimeout=3",
    "-o",
    "LogLevel=ERROR",
]


@dataclass
class ExecResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass
class ClawVM:
    name: str
    vmm: str
    accel: str | None
    ssh_user: str
    ssh_port: int | None
    ssh_host: str
    disk: Path
    r2_isolated: bool = True

    def exec(self, command: str | list[str], timeout: int = 60) -> ExecResult:
        return exec_in(self.name, command, timeout=timeout)

    def stop(self) -> None:
        stop(self.name)

    def doctor(self) -> dict[str, object]:
        return status(self.name)

    def isolation(self) -> dict[str, object]:
        return isolation_report(vmm=self.vmm, accel=self.accel)


def _meta_path(name: str) -> Path:
    return instance_dir(name) / "meta.json"


def _read_meta(name: str) -> dict[str, Any]:
    path = _meta_path(name)
    if not path.is_file():
        raise FileNotFoundError(f"no VM named {name!r} (missing {path})")
    return json.loads(path.read_text())


def _write_meta(name: str, meta: dict[str, Any]) -> None:
    path = _meta_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2) + "\n")


def _image(image_id: str | None, vmm: str) -> Image:
    iid = (image_id or os.environ.get("CLAW_VM_IMAGE") or default_image_id(vmm)).lower()
    if iid not in IMAGES:
        raise ValueError(f"unknown image {iid!r}; known: {', '.join(IMAGES)}")
    img = IMAGES[iid]
    if vmm == "firecracker" and img.vmm != "firecracker":
        return IMAGES["fc-ubuntu"]
    if vmm == "qemu" and img.vmm != "qemu":
        return IMAGES["alpine"]
    return img


def _ssh_port_for(name: str) -> int:
    return 2200 + (sum(name.encode()) % 700)


def start(
    name: str = "agent",
    *,
    image: str | None = None,
    vmm: str | None = None,
    backend: str | None = None,
    wait: bool = True,
    timeout: int = 180,
) -> ClawVM:
    name = check_name(name)
    requested = backend or vmm
    bid = resolve_backend(requested)
    if bid not in BUILTIN_VMMS:
        payload = start_backend(bid, name)
        return _optional_started(name, bid, payload)
    if bid == "firecracker":
        live = live_start_for("firecracker")
        if not live.ready:
            raise StartSkipped("firecracker", live.reason, live.detail)
    chosen = bid
    img = _image(image, chosen)
    idir = instance_dir(name)
    idir.mkdir(parents=True, exist_ok=True)
    if _meta_path(name).is_file():
        meta = _read_meta(name)
        pid = int(meta.get("pid") or 0)
        if pid and pid_alive(pid):
            return _from_meta(meta)
        # leftover meta from a dead VM: reuse the disk (persistence) but restart VMM

    fetch_assets(image=img.id, vmm=chosen)
    ensure_ssh_key()

    if chosen == "firecracker":
        meta = _start_firecracker(name, img)
    else:
        meta = _start_qemu(name, img, vmm_request=vmm)

    _write_meta(name, meta)
    vm = _from_meta(meta)
    if wait:
        _wait_ssh(vm, timeout=timeout)
        meta["ssh_ready"] = True
        _write_meta(name, meta)
    return vm


def _start_qemu(name: str, img: Image, *, vmm_request: str | None) -> dict[str, Any]:
    idir = instance_dir(name)
    if img.id == "alpine":
        from .bake import bake_alpine, baked_alpine_path

        bake_alpine()
        template = baked_alpine_path()
    else:
        template = fetch_qemu_image(img)
    disk = overlay_disk(template, idir / "disk.qcow2")
    pub = ssh_pub_path().read_text().strip()
    seed = write_cidata_iso(
        idir / "cidata.img",
        hostname=name,
        ssh_pub=pub,
        image_id=img.id,
    )
    port = _ssh_port_for(name)
    serial = idir / "serial.log"
    qlog = idir / "qemu.log"
    pidfile = idir / "qemu.pid"
    monitor = idir / "monitor.sock"
    if monitor.exists():
        monitor.unlink()
    force = None
    if (vmm_request or "").lower() in {"qemu-kvm"}:
        force = "kvm"
    elif (vmm_request or "").lower() in {"qemu-tcg", "qemu"}:
        force = "tcg" if not vcpu_known_good() else None
    accel, cmd = qemu_argv(
        disk=disk,
        seed_iso=seed,
        serial_log=serial,
        qemu_log=qlog,
        pidfile=pidfile,
        ssh_port=port,
        mem_mib=img.mem_mib,
        accel_force=force,
        monitor_sock=monitor,
    )
    (idir / "qemu.argv").write_text(" ".join(cmd) + "\n")
    proc = start_qemu(cmd, log=qlog)
    time.sleep(0.3)
    if proc.poll() is not None:
        raise RuntimeError(
            f"qemu exited {proc.returncode}; see {qlog} and {serial}"
        )
    pid = proc.pid
    if pidfile.is_file():
        try:
            pid = int(pidfile.read_text().strip() or pid)
        except ValueError:
            pass
    iso = isolation_report(vmm="qemu", accel=accel)
    return {
        "name": name,
        "vmm": "qemu",
        "accel": accel,
        "image": img.id,
        "ssh_user": img.ssh_user,
        "ssh_host": "127.0.0.1",
        "ssh_port": port,
        "disk": str(disk),
        "pid": pid,
        "monitor": str(monitor),
        "r2_isolated": True,
        "r2_hardware_kvm": bool(iso["r2_hardware_kvm"]),
        "started_at": time.time(),
    }


def _start_firecracker(name: str, img: Image) -> dict[str, Any]:
    if not vcpu_known_good() and os.environ.get("CLAW_VM_FORCE_FIRECRACKER") != "1":
        raise RuntimeError(
            "Firecracker needs KVM_CREATE_VCPU. On this nested host that ioctl "
            "kernel-BUGs (alloc_loaded_vmcs). Default VMM is QEMU TCG. To try "
            "anyway: CLAW_VM_FORCE_FIRECRACKER=1 claw-vm start --vmm firecracker"
        )
    idir = instance_dir(name)
    if not fc_ext4_template().is_file():
        build_fc_ext4()
    disk = copy_rootfs(fc_ext4_template(), idir / "disk.ext4")
    slot = slot_from_name(name)
    tap = tap_name(name)
    mac = guest_mac(slot)
    hip = host_ip(slot)
    gip = guest_ip(slot)
    setup_tap(tap, hip)
    log = idir / "firecracker.log"
    sock = idir / "firecracker.sock"
    cfg = firecracker_config(
        kernel=kernel_path(),
        rootfs=disk,
        tap=tap,
        mac=mac,
        mem_mib=img.mem_mib,
        log_path=log,
    )
    cfg_path = write_config(idir / "vm.json", cfg)
    proc = start_firecracker(config_path=cfg_path, sock_path=sock, log_path=log)
    time.sleep(0.4)
    if proc.poll() is not None:
        teardown_tap(tap)
        raise RuntimeError(
            f"firecracker exited {proc.returncode}; see {log}"
        )
    iso = isolation_report(vmm="firecracker", accel="kvm")
    return {
        "name": name,
        "vmm": "firecracker",
        "accel": "kvm",
        "image": img.id,
        "ssh_user": img.ssh_user,
        "ssh_host": gip,
        "ssh_port": 22,
        "tap": tap,
        "mac": mac,
        "disk": str(disk),
        "pid": proc.pid,
        "r2_isolated": True,
        "r2_hardware_kvm": bool(iso["r2_hardware_kvm"]),
        "started_at": time.time(),
    }


def _optional_started(name: str, bid: str, payload: dict[str, Any]) -> ClawVM:
    """Record a successful optional-backend start. Skip paths never reach here."""
    idir = instance_dir(name)
    idir.mkdir(parents=True, exist_ok=True)
    iso = isolation_report(vmm=bid, accel="kvm")
    disk = idir / "disk"
    meta = {
        "name": name,
        "vmm": bid,
        "accel": "kvm",
        "image": bid,
        "ssh_user": "root",
        "ssh_host": "127.0.0.1",
        "ssh_port": None,
        "disk": str(disk),
        "pid": None,
        "r2_isolated": True,
        "r2_hardware_kvm": bool(iso["r2_hardware_kvm"]),
        "optional": True,
        "backend_start": payload,
        "started_at": time.time(),
    }
    _write_meta(name, meta)
    return _from_meta(meta)


def _from_meta(meta: dict[str, Any]) -> ClawVM:
    return ClawVM(
        name=str(meta["name"]),
        vmm=str(meta["vmm"]),
        accel=meta.get("accel"),
        ssh_user=str(meta["ssh_user"]),
        ssh_port=int(meta["ssh_port"]) if meta.get("ssh_port") else None,
        ssh_host=str(meta["ssh_host"]),
        disk=Path(str(meta["disk"])),
        r2_isolated=bool(meta.get("r2_isolated", True)),
    )


def _ssh_base(vm: ClawVM) -> list[str]:
    cmd = ["ssh", *SSH_OPTS, "-i", str(ssh_key_path())]
    if vm.ssh_port:
        cmd.extend(["-p", str(vm.ssh_port)])
    cmd.append(f"{vm.ssh_user}@{vm.ssh_host}")
    return cmd


def ssh_remote(command: str | list[str]) -> str:
    """Single ssh operand. OpenSSH joins extra argv with spaces and does not quote."""
    if isinstance(command, list):
        return shlex.join(command)
    return command


def _wait_ssh(vm: ClawVM, *, timeout: int) -> None:
    users = [vm.ssh_user]
    for extra in ("claw", "alpine", "root", "cirros", "ubuntu"):
        if extra not in users:
            users.append(extra)
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        for user in users:
            trial = ClawVM(
                name=vm.name,
                vmm=vm.vmm,
                accel=vm.accel,
                ssh_user=user,
                ssh_port=vm.ssh_port,
                ssh_host=vm.ssh_host,
                disk=vm.disk,
            )
            proc = subprocess.run(
                [*_ssh_base(trial), "true"],
                check=False,
                text=True,
                capture_output=True,
                timeout=8,
            )
            if proc.returncode == 0:
                if user != vm.ssh_user:
                    meta = _read_meta(vm.name)
                    meta["ssh_user"] = user
                    _write_meta(vm.name, meta)
                    vm.ssh_user = user
                return
            last = (proc.stderr or proc.stdout or "")[-200:]
        time.sleep(3)
    raise TimeoutError(
        f"SSH into {vm.name} ({vm.ssh_user}@{vm.ssh_host}:{vm.ssh_port}) "
        f"did not become ready in {timeout}s. Last error: {last!r}. "
        f"Serial: {instance_dir(vm.name) / 'serial.log'}"
    )


def exec_in(
    name: str,
    command: str | list[str],
    *,
    timeout: int = 60,
) -> ExecResult:
    meta = _read_meta(name)
    vm = _from_meta(meta)
    proc = subprocess.run(
        [*_ssh_base(vm), ssh_remote(command)],
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return ExecResult(proc.returncode, proc.stdout, proc.stderr)


def stop(name: str) -> None:
    name = check_name(name)
    try:
        meta = _read_meta(name)
    except FileNotFoundError:
        return
    pid = int(meta.get("pid") or 0)
    if meta.get("monitor"):
        monitor_quit(Path(str(meta["monitor"])))
        time.sleep(0.4)
    if pid:
        stop_pid(pid, timeout=15)
    if meta.get("tap"):
        teardown_tap(str(meta["tap"]))
    meta["pid"] = None
    meta["stopped_at"] = time.time()
    _write_meta(name, meta)


def destroy(name: str) -> None:
    stop(name)
    path = instance_dir(name)
    if path.is_dir():
        shutil.rmtree(path)


def status(name: str | None = None) -> dict[str, object]:
    if name:
        meta = _read_meta(name)
        pid = int(meta.get("pid") or 0)
        meta["running"] = bool(pid and pid_alive(pid))
        meta["isolation"] = isolation_report(
            vmm=str(meta.get("vmm") or "qemu"),
            accel=meta.get("accel"),
        )
        return meta
    instances_dir().mkdir(parents=True, exist_ok=True)
    items = []
    for child in sorted(instances_dir().iterdir()):
        if (child / "meta.json").is_file():
            items.append(status(child.name))
    return {"instances": items}


def persist_probe(name: str) -> dict[str, object]:
    """Write a guest file, stop VMM, start again, read it back."""
    marker = "/root/claw-persist-marker"
    payload = f"claw-persist-{name}-{os.getpid()}"
    first = exec_in(
        name,
        f"printf '%s\\n' '{payload}' > {marker} && sync && cat {marker}",
    )
    if first.returncode != 0 or payload not in first.stdout:
        raise RuntimeError(
            f"guest write failed: rc={first.returncode} "
            f"stdout={first.stdout!r} stderr={first.stderr!r}"
        )
    meta = _read_meta(name)
    vmm = str(meta["vmm"])
    image = str(meta.get("image") or "")
    stop(name)
    time.sleep(2)
    start(name, image=image, vmm=vmm, wait=True)
    second = exec_in(name, f"cat {marker}")
    return {
        "marker": marker,
        "wrote": payload,
        "read": second.stdout.strip(),
        "ok": second.returncode == 0 and payload in second.stdout,
    }
