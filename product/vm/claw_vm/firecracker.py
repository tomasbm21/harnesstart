"""Firecracker backend. Needs working KVM_CREATE_VCPU (not true on this nested host)."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from . import priv
from .assets import firecracker_bin
from .kvm import ensure_kvm_acl, kvm_openable


def firecracker_config(
    *,
    kernel: Path,
    rootfs: Path,
    tap: str,
    mac: str,
    mem_mib: int,
    log_path: Path,
) -> dict[str, Any]:
    return {
        "boot-source": {
            "kernel_image_path": str(kernel),
            "boot_args": "console=ttyS0 reboot=k panic=1 pci=off",
        },
        "drives": [
            {
                "drive_id": "rootfs",
                "path_on_host": str(rootfs),
                "is_root_device": True,
                "is_read_only": False,
            }
        ],
        "machine-config": {
            "vcpu_count": 1,
            "mem_size_mib": mem_mib,
            "smt": False,
        },
        "network-interfaces": [
            {
                "iface_id": "net1",
                "guest_mac": mac,
                "host_dev_name": tap,
            }
        ],
        "logger": {
            "log_path": str(log_path),
            "level": "Info",
            "show_level": True,
            "show_log_origin": False,
        },
    }


def slot_from_name(name: str) -> int:
    return 1 + (sum(name.encode()) % 200)


def tap_name(name: str) -> str:
    # IFNAMSIZ is 16 including NUL
    raw = f"fc-{name}"
    return raw[:15]


def guest_mac(slot: int) -> str:
    return f"06:00:ac:10:{slot:02x}:02"


def guest_ip(slot: int) -> str:
    return f"172.16.{slot}.2"


def host_ip(slot: int) -> str:
    return f"172.16.{slot}.1"


def setup_tap(tap: str, host: str) -> None:
    if not priv.have("ip"):
        raise RuntimeError("iproute2 missing")
    priv.run(["ip", "link", "del", tap], privileged=True, check=False)
    priv.run(["ip", "tuntap", "add", "dev", tap, "mode", "tap"], privileged=True)
    priv.run(["ip", "addr", "add", f"{host}/30", "dev", tap], privileged=True)
    priv.run(["ip", "link", "set", "dev", tap, "up"], privileged=True)


def teardown_tap(tap: str) -> None:
    if priv.have("ip"):
        priv.run(["ip", "link", "del", tap], privileged=True, check=False)


def start_firecracker(
    *,
    config_path: Path,
    sock_path: Path,
    log_path: Path,
) -> subprocess.Popen[bytes]:
    ensure_kvm_acl()
    bin_path = firecracker_bin()
    if not bin_path.is_file():
        raise RuntimeError("firecracker binary missing; run claw-vm fetch --vmm firecracker")
    if sock_path.exists():
        sock_path.unlink()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("")
    argv = [
        str(bin_path),
        "--api-sock",
        str(sock_path),
        "--config-file",
        str(config_path),
    ]
    privileged = not kvm_openable()
    if privileged:
        argv = ["sudo", "-n", *argv]
    log_f = log_path.open("ab")
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=log_f,
        stderr=log_f,
        start_new_session=True,
    )
    return proc


def wait_api(sock: Path, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if sock.exists():
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(0.2)
                s.connect(str(sock))
                s.close()
                return True
            except OSError:
                pass
        time.sleep(0.05)
    return False


def copy_rootfs(template: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        return dest
    # persistent per-instance writable disk
    with template.open("rb") as src, dest.open("wb") as out:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    return dest


def write_config(path: Path, cfg: dict[str, Any]) -> Path:
    path.write_text(json.dumps(cfg, indent=2) + "\n")
    return path
