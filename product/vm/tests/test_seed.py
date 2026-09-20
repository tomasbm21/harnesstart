from __future__ import annotations

import unittest

import _path  # noqa: F401
from claw_vm.seed import _user_data


class SeedTest(unittest.TestCase):
    def test_alpine_cloud_config(self) -> None:
        text = _user_data(image_id="alpine", hostname="agent", ssh_pub="ssh-ed25519 AAAA")
        self.assertTrue(text.startswith("#cloud-config"))
        self.assertIn("ssh-ed25519 AAAA", text)
        self.assertIn("name: claw", text)

    def test_cirros_shell(self) -> None:
        text = _user_data(image_id="cirros", hostname="agent", ssh_pub="ssh-ed25519 AAAA")
        self.assertTrue(text.startswith("#!/bin/sh"))
        self.assertIn("ssh-ed25519 AAAA", text)
