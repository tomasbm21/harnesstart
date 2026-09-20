"""Pinned guest/VMM artifacts. No Docker. Downloads are official upstream files."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import priv
from .paths import assets_dir

FIRECRACKER_VERSION = "1.16.1"
FIRECRACKER_TGZ = (
    f"https://github.com/firecracker-microvm/firecracker/releases/download/"
    f"v{FIRECRACKER_VERSION}/firecracker-v{FIRECRACKER_VERSION}-x86_64.tgz"
)
# Versioned Firecracker CI prefix (v1.16 was empty on 2026-09-20).
FC_KERNEL_URL = (
    "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.15/x86_64/vmlinux-6.1.155"
)
FC_ROOTFS_URL = (
    "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.15/x86_64/ubuntu-24.04.squashfs"
)
ALPINE_URL = (
    "https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/cloud/"
    "generic_alpine-3.21.5-x86_64-bios-cloudinit-r0.qcow2"
)
CIRROS_URL = (
    "https://github.com/cirros-dev/cirros/releases/download/0.6.2/"
    "cirros-0.6.2-x86_64-disk.img"
)

HOST_PACKAGES = (
    "qemu-system-x86",
    "qemu-utils",
    "genisoimage",
    "dosfstools",
    "mtools",
    "squashfs-tools",
    "iproute2",
    "e2fsprogs",
    "acl",
    "openssh-client",
)


@dataclass(frozen=True)
class Image:
    id: str
    vmm: str  # firecracker | qemu
    url: str
    filename: str
    ssh_user: str
    mem_mib: int
    note: str


IMAGES = {
    "alpine": Image(
        id="alpine",
        vmm="qemu",
        url=ALPINE_URL,
        filename="generic_alpine-3.21.5-x86_64-bios-cloudinit-r0.qcow2",
        ssh_user="root",
        mem_mib=512,
        note="Alpine 3.21 cloud (NoCloud). Default QEMU guest.",
    ),
    "cirros": Image(
        id="cirros",
        vmm="qemu",
        url=CIRROS_URL,
        filename="cirros-0.6.2-x86_64-disk.img",
        ssh_user="cirros",
        mem_mib=256,
        note="Tiny QEMU smoke image.",
    ),
    "fc-ubuntu": Image(
        id="fc-ubuntu",
        vmm="firecracker",
        url=FC_ROOTFS_URL,
        filename="ubuntu-24.04.squashfs",
        ssh_user="root",
        mem_mib=256,
        note="Firecracker CI Ubuntu 24.04 squashfs → persistent ext4.",
    ),
}


def default_image_id(vmm: str) -> str:
    return "fc-ubuntu" if vmm == "firecracker" else "alpine"


def firecracker_bin() -> Path:
    return assets_dir() / "firecracker"


def jailer_bin() -> Path:
    return assets_dir() / "jailer"


def kernel_path() -> Path:
    return assets_dir() / "vmlinux-6.1.155"


def fc_squashfs_path() -> Path:
    return assets_dir() / "ubuntu-24.04.squashfs"


def fc_ext4_template() -> Path:
    return assets_dir() / "ubuntu-24.04.ext4"


def qemu_image_path(image: Image) -> Path:
    return assets_dir() / image.filename


def ssh_key_path() -> Path:
    return assets_dir() / "id_ed25519"


def ssh_pub_path() -> Path:
    return assets_dir() / "id_ed25519.pub"


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "claw-vm/0.1"})
    with urllib.request.urlopen(req, timeout=120) as resp, tmp.open("wb") as out:
        shutil.copyfileobj(resp, out)
    tmp.replace(dest)
    return dest


def ensure_ssh_key() -> tuple[Path, Path]:
    priv_key = ssh_key_path()
    pub = ssh_pub_path()
    if priv_key.is_file() and pub.is_file():
        return priv_key, pub
    assets_dir().mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(priv_key), "-q"],
        check=True,
    )
    os.chmod(priv_key, stat.S_IRUSR | stat.S_IWUSR)
    return priv_key, pub


def ensure_host_packages() -> list[str]:
    """Install missing packages used to build disks / run QEMU. No Docker."""
    missing: list[str] = []
    mapping = {
        "qemu-system-x86": "qemu-system-x86_64",
        "qemu-utils": "qemu-img",
        "genisoimage": "genisoimage",
        "dosfstools": "mkfs.vfat",
        "mtools": "mcopy",
        "squashfs-tools": "unsquashfs",
        "iproute2": "ip",
        "e2fsprogs": "mkfs.ext4",
        "acl": "setfacl",
        "openssh-client": "ssh",
    }
    for pkg, cmd in mapping.items():
        if not priv.have(cmd):
            missing.append(pkg)
    if not missing:
        return []
    if not priv.can_sudo():
        raise RuntimeError(
            "missing packages: " + ", ".join(missing) + " (need sudo to apt install)"
        )
    priv.run(
        ["apt-get", "install", "-y", *missing],
        privileged=True,
    )
    return missing


def fetch_firecracker() -> dict[str, str]:
    tgz = assets_dir() / f"firecracker-v{FIRECRACKER_VERSION}-x86_64.tgz"
    download(FIRECRACKER_TGZ, tgz)
    dest_fc = firecracker_bin()
    dest_jailer = jailer_bin()
    if not dest_fc.is_file():
        with tarfile.open(tgz, "r:gz") as tf:
            with tempfile.TemporaryDirectory() as td:
                tf.extractall(td, filter="data")
                root = Path(td)
                fc = next(root.rglob(f"firecracker-v{FIRECRACKER_VERSION}-x86_64"))
                jailer = next(root.rglob(f"jailer-v{FIRECRACKER_VERSION}-x86_64"))
                shutil.copy2(fc, dest_fc)
                shutil.copy2(jailer, dest_jailer)
        os.chmod(dest_fc, dest_fc.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.chmod(dest_jailer, dest_jailer.stat().st_mode | stat.S_IXUSR)
    download(FC_KERNEL_URL, kernel_path())
    download(FC_ROOTFS_URL, fc_squashfs_path())
    return {
        "firecracker": str(dest_fc),
        "jailer": str(dest_jailer),
        "kernel": str(kernel_path()),
        "squashfs": str(fc_squashfs_path()),
    }


def build_fc_ext4() -> Path:
    """Convert CI squashfs → writable ext4 template with our SSH key. No Docker."""
    out = fc_ext4_template()
    if out.is_file() and out.stat().st_size > 0:
        return out
    if not priv.have("unsquashfs") or not priv.have("mkfs.ext4"):
        ensure_host_packages()
    _, pub = ensure_ssh_key()
    pub_text = pub.read_text().strip()
    squash = fc_squashfs_path()
    if not squash.is_file():
        fetch_firecracker()
    work = Path(tempfile.mkdtemp(prefix="claw-vm-rootfs-"))
    try:
        subprocess.run(
            ["unsquashfs", "-d", str(work / "root"), str(squash)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        root = work / "root"
        ssh_dir = root / "root" / ".ssh"
        ssh_dir.mkdir(parents=True, exist_ok=True)
        auth = ssh_dir / "authorized_keys"
        existing = auth.read_text() if auth.is_file() else ""
        if pub_text not in existing:
            auth.write_text(existing + pub_text + "\n")
        os.chmod(ssh_dir, 0o700)
        os.chmod(auth, 0o600)
        raw = work / "disk.ext4"
        subprocess.run(["truncate", "-s", "2G", str(raw)], check=True)
        mkfs = ["mkfs.ext4", "-F", "-L", "clawroot", "-d", str(root), str(raw)]
        if os.geteuid() != 0:
            mkfs = ["sudo", "-n", *mkfs]
        subprocess.run(mkfs, check=True, stdout=subprocess.DEVNULL)
        shutil.move(str(raw), out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out


def fetch_qemu_image(image: Image) -> Path:
    dest = qemu_image_path(image)
    download(image.url, dest)
    return dest


def fetch_assets(*, image: str | None = None, vmm: str | None = None) -> dict[str, object]:
    ensure_host_packages()
    ensure_ssh_key()
    vmm = (vmm or os.environ.get("CLAW_VM_VMM") or "auto").lower()
    image_id = image or os.environ.get("CLAW_VM_IMAGE")
    out: dict[str, object] = {"home": str(assets_dir()), "installed_packages": True}

    want_qemu = vmm in {"auto", "qemu", "all"}
    want_fc = vmm in {"firecracker", "all"}
    if want_qemu:
        img = IMAGES[(image_id if image_id in IMAGES else None) or "alpine"]
        if img.vmm != "qemu":
            img = IMAGES["alpine"]
        if img.id == "alpine":
            from .bake import bake_alpine, baked_alpine_path

            path = bake_alpine()
            out["qemu_image"] = str(path)
            out["qemu_baked"] = str(baked_alpine_path())
        else:
            path = fetch_qemu_image(img)
            out["qemu_image"] = str(path)
        out["qemu_image_id"] = img.id
    if want_fc:
        out["firecracker"] = fetch_firecracker()
        out["fc_ext4"] = str(build_fc_ext4())

    pub = ssh_pub_path().read_text().strip()
    out["ssh_fingerprint"] = hashlib.sha256(pub.encode()).hexdigest()[:16]
    return out
