from __future__ import annotations

import unittest

from norfront_claw.computer import HostComputer


class ComputerTest(unittest.TestCase):
    def test_host_is_not_r2(self) -> None:
        c = HostComputer()
        self.assertFalse(c.r2_isolated)
        info = c.doctor()
        self.assertFalse(info["r2_isolated"])
        self.assertIn("Firecracker", str(info["stub"]))


if __name__ == "__main__":
    unittest.main()
