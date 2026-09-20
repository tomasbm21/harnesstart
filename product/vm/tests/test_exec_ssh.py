from __future__ import annotations

import unittest

import _path  # noqa: F401
from claw_vm.instance import ssh_remote


class SshRemoteTest(unittest.TestCase):
    def test_redirect_stays_one_operand(self) -> None:
        script = "printf '%s\\n' 'payload' > /root/claw-persist-marker && sync && cat /root/claw-persist-marker"
        remote = ssh_remote(script)
        self.assertEqual(remote, script)
        self.assertNotIn("sh -lc", remote)

    def test_list_is_joined(self) -> None:
        self.assertEqual(ssh_remote(["uname", "-a"]), "uname -a")


if __name__ == "__main__":
    unittest.main()
