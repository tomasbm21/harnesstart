"""cloud-init NoCloud CIDATA volume (VFAT). No Docker.

ISO 9660 8.3 names turn user-data into USER_DAT.;1, which CirrOS ignores.
A VFAT filesystem labeled CIDATA keeps the real filenames.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from . import priv


def write_cidata_iso(
    dest: Path,
    *,
    hostname: str,
    ssh_pub: str,
    image_id: str,
) -> Path:
    """Write a VFAT cidata image. Name kept for call-site stability."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    user_data = _user_data(image_id=image_id, hostname=hostname, ssh_pub=ssh_pub)
    meta = f"instance-id: claw-{hostname}\nlocal-hostname: {hostname}\n"
    if not priv.have("mkfs.vfat") or not priv.have("mcopy"):
        raise RuntimeError("dosfstools/mtools missing; run claw-vm fetch")
    dest.write_bytes(b"\x00" * (2 * 1024 * 1024))
    subprocess.run(
        ["mkfs.vfat", "-n", "CIDATA", "-I", str(dest)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with tempfile.TemporaryDirectory(prefix="claw-cidata-") as td:
        tdp = Path(td)
        (tdp / "user-data").write_text(user_data)
        (tdp / "meta-data").write_text(meta)
        files = ["user-data", "meta-data"]
        if image_id != "cirros":
            (tdp / "network-config").write_text(
                "version: 2\nethernets:\n  id0:\n    match:\n      name: \"e*\"\n"
                "    dhcp4: true\n"
            )
            files.append("network-config")
        for name in files:
            subprocess.run(
                ["mcopy", "-i", str(dest), "-o", str(tdp / name), f"::{name}"],
                check=True,
            env={**os.environ, "MTOOLS_SKIP_CHECK": "1"},
            )
    if dest.stat().st_size < 1024:
        raise RuntimeError("cidata image too small")
    return dest


def _user_data(*, image_id: str, hostname: str, ssh_pub: str) -> str:
    if image_id == "cirros":
        return (
            "#!/bin/sh\n"
            "mkdir -p /home/cirros/.ssh /root/.ssh\n"
            f"printf '%s\\n' '{ssh_pub}' >> /home/cirros/.ssh/authorized_keys\n"
            f"printf '%s\\n' '{ssh_pub}' >> /root/.ssh/authorized_keys\n"
            "chown -R cirros:cirros /home/cirros/.ssh 2>/dev/null || true\n"
            "chmod 700 /home/cirros/.ssh /root/.ssh\n"
            "chmod 600 /home/cirros/.ssh/authorized_keys /root/.ssh/authorized_keys\n"
            "mkdir -p /var/lib/claw\n"
            "echo ready > /var/lib/claw/ready\n"
        )
    return f"""#cloud-config
hostname: {hostname}
manage_etc_hosts: true
ssh_pwauth: false
disable_root: false
users:
  - name: claw
    gecos: Norfront Claw
    shell: /bin/sh
    lock_passwd: true
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - {ssh_pub}
  - name: alpine
    lock_passwd: true
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - {ssh_pub}
  - name: root
    lock_passwd: true
    ssh_authorized_keys:
      - {ssh_pub}
runcmd:
  - mkdir -p /var/lib/claw /root/.ssh
  - echo ready > /var/lib/claw/ready
  - printf '%s\n' '{ssh_pub}' >> /root/.ssh/authorized_keys
  - chmod 700 /root/.ssh
  - chmod 600 /root/.ssh/authorized_keys
  - rc-update add sshd default || true
  - rc-service sshd start || /usr/sbin/sshd || true
"""
