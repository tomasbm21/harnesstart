from __future__ import annotations

import json
import unittest
from pathlib import Path

import _path  # noqa: F401
from claw_vm.firecracker import firecracker_config, guest_ip, guest_mac, host_ip, slot_from_name, tap_name


class FirecrackerConfigTest(unittest.TestCase):
    def test_slot_and_net(self) -> None:
        slot = slot_from_name("agent")
        self.assertTrue(1 <= slot <= 200)
        mac = guest_mac(slot)
        self.assertTrue(mac.startswith("06:00:ac:10:"))
        self.assertEqual(guest_ip(slot), f"172.16.{slot}.2")
        self.assertEqual(host_ip(slot), f"172.16.{slot}.1")
        self.assertLessEqual(len(tap_name("agent")), 15)

    def test_config_json(self) -> None:
        cfg = firecracker_config(
            kernel=Path("/tmp/vmlinux"),
            rootfs=Path("/tmp/root.ext4"),
            tap="fc-agent",
            mac="06:00:ac:10:01:02",
            mem_mib=256,
            log_path=Path("/tmp/fc.log"),
        )
        raw = json.dumps(cfg)
        self.assertIn("boot-source", cfg)
        self.assertTrue(cfg["drives"][0]["is_root_device"])
        self.assertFalse(cfg["drives"][0]["is_read_only"])
        self.assertEqual(cfg["network-interfaces"][0]["host_dev_name"], "fc-agent")
        self.assertIn("console=ttyS0", cfg["boot-source"]["boot_args"])
        self.assertNotIn("docker", raw.lower())


if __name__ == "__main__":
    unittest.main()
