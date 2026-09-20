from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _path  # noqa: F401
from claw_vm.qemu import argv, overlay_disk


class QemuArgvTest(unittest.TestCase):
    def test_restrict_and_hostfwd(self) -> None:
        with patch("claw_vm.qemu.vcpu_known_good", return_value=False):
            accel, cmd = argv(
                disk=Path("/tmp/disk.qcow2"),
                seed_iso=Path("/tmp/cidata.iso"),
                serial_log=Path("/tmp/serial.log"),
                qemu_log=Path("/tmp/qemu.log"),
                pidfile=Path("/tmp/qemu.pid"),
                ssh_port=2222,
                mem_mib=512,
                accel_force="tcg",
            )
        joined = " ".join(cmd)
        self.assertEqual(accel, "tcg")
        self.assertIn("hostfwd=tcp:127.0.0.1:2222-:22", joined)
        self.assertIn("-accel tcg", joined)
        self.assertIn("format=raw", joined)
        self.assertIn("cache=writethrough", joined)
        self.assertNotIn("docker", joined)

    def test_monitor_sock(self) -> None:
        accel, cmd = argv(
            disk=Path("/tmp/disk.qcow2"),
            seed_iso=None,
            serial_log=Path("/tmp/serial.log"),
            qemu_log=Path("/tmp/qemu.log"),
            pidfile=Path("/tmp/qemu.pid"),
            ssh_port=2727,
            mem_mib=512,
            accel_force="tcg",
            monitor_sock=Path("/tmp/monitor.sock"),
        )
        self.assertEqual(accel, "tcg")
        self.assertIn("unix:/tmp/monitor.sock,server=on,wait=off", " ".join(cmd))

    def test_overlay_creates_qcow2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "base.qcow2"
            dest = Path(td) / "overlay.qcow2"
            import subprocess

            subprocess.run(
                ["qemu-img", "create", "-f", "qcow2", str(base), "8M"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            overlay_disk(base, dest, size="16M")
            self.assertTrue(dest.is_file())
            overlay_disk(base, dest, size="16M")  # idempotent


if __name__ == "__main__":
    unittest.main()
