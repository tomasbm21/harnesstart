"""Bake SSH into the Alpine qcow2 so the guest does not depend on cloud-init."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import textwrap
from pathlib import Path

from . import priv
from .assets import IMAGES, fetch_qemu_image, ssh_pub_path
from .paths import assets_dir


def baked_alpine_path() -> Path:
    return assets_dir() / "alpine-3.21.5-baked.qcow2"


def bake_alpine(*, ssh_pub: str | None = None) -> Path:
    dest = baked_alpine_path()
    pub = (ssh_pub or ssh_pub_path().read_text()).strip()
    marker = dest.with_suffix(".pubsha")
    if dest.is_file() and marker.is_file() and marker.read_text().strip() == pub:
        return dest
    if not priv.can_sudo():
        raise RuntimeError("sudo required to bake SSH keys into the Alpine image")

    img = fetch_qemu_image(IMAGES["alpine"])
    fd, raw_name = tempfile.mkstemp(prefix="claw-alpine-", suffix=".raw")
    os.close(fd)
    raw = Path(raw_name)
    pubfile = Path(tempfile.mkstemp(prefix="claw-ssh-", suffix=".pub")[1])
    pubfile.write_text(pub + "\n")
    try:
        subprocess.run(["qemu-img", "convert", "-O", "raw", str(img), str(raw)], check=True)
        script = textwrap.dedent(
            f"""\
            set -euo pipefail
            cleanup() {{
              umount "$MNT" 2>/dev/null || true
              rmdir "$MNT" 2>/dev/null || true
              [ -n "${{LOOP:-}}" ] && losetup -d "$LOOP" 2>/dev/null || true
            }}
            trap cleanup EXIT
            LOOP=$(losetup -f --show {raw})
            MNT=$(mktemp -d)
            mount "$LOOP" "$MNT"
            mkdir -p "$MNT/root/.ssh" "$MNT/home/claw/.ssh" "$MNT/etc/cloud" \\
                     "$MNT/etc/sudoers.d" "$MNT/var/lib/claw"
            cp {pubfile} "$MNT/root/.ssh/authorized_keys"
            cp {pubfile} "$MNT/home/claw/.ssh/authorized_keys"
            chmod 700 "$MNT/root/.ssh" "$MNT/home/claw/.ssh"
            chmod 600 "$MNT/root/.ssh/authorized_keys" "$MNT/home/claw/.ssh/authorized_keys"
            grep -q '^claw:' "$MNT/etc/passwd" || echo 'claw:x:1000:1000:claw:/home/claw:/bin/sh' >> "$MNT/etc/passwd"
            grep -q '^claw:' "$MNT/etc/group" || echo 'claw:x:1000:' >> "$MNT/etc/group"
            grep -q '^claw:' "$MNT/etc/shadow" || echo 'claw:!:18000:0:99999:7:::' >> "$MNT/etc/shadow"
            echo 'claw ALL=(ALL) NOPASSWD: ALL' > "$MNT/etc/sudoers.d/claw"
            chmod 440 "$MNT/etc/sudoers.d/claw"
            chown -R 0:0 "$MNT/root/.ssh"
            chown -R 1000:1000 "$MNT/home/claw"
            # OpenSSH refuses pubkey login when the shadow password is ! or *.
            sed -i 's/^root:[^:]*/root:x/' "$MNT/etc/shadow"
            sed -i 's/^claw:[^:]*/claw:x/' "$MNT/etc/shadow"
            echo 'claw-vm' > "$MNT/etc/cloud/cloud-init.disabled"
            echo baked > "$MNT/var/lib/claw/ready"
            if [ -f "$MNT/etc/ssh/sshd_config" ]; then
              if grep -q '^PermitRootLogin' "$MNT/etc/ssh/sshd_config"; then
                sed -i 's/^PermitRootLogin.*/PermitRootLogin prohibit-password/' "$MNT/etc/ssh/sshd_config"
              else
                echo 'PermitRootLogin prohibit-password' >> "$MNT/etc/ssh/sshd_config"
              fi
              echo 'PerSourcePenalties no' >> "$MNT/etc/ssh/sshd_config"
            fi
            if [ -x "$MNT/etc/init.d/sshd" ] && [ ! -e "$MNT/etc/runlevels/default/sshd" ] && [ ! -L "$MNT/etc/runlevels/default/sshd" ]; then
              ln -s /etc/init.d/sshd "$MNT/etc/runlevels/default/sshd"
            fi
            if [ -x "$MNT/usr/bin/ssh-keygen" ] && ! ls "$MNT/etc/ssh/ssh_host_"* >/dev/null 2>&1; then
              chroot "$MNT" /usr/bin/ssh-keygen -A
            fi
            """
        )
        try:
            priv.run(["bash", "-c", script], privileged=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("failed to bake SSH into Alpine image") from exc
        tmp_q = dest.with_suffix(".qcow2.tmp")
        subprocess.run(
            ["qemu-img", "convert", "-c", "-O", "qcow2", str(raw), str(tmp_q)],
            check=True,
        )
        tmp_q.replace(dest)
        marker.write_text(pub + "\n")
        os.chmod(dest, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    finally:
        raw.unlink(missing_ok=True)
        pubfile.unlink(missing_ok=True)
    return dest
