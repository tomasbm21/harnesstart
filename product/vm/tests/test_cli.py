from __future__ import annotations

import json
import unittest
from io import StringIO
from unittest.mock import patch

import _path  # noqa: F401
from claw_vm.cli import main


class CliTest(unittest.TestCase):
    def test_version(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["--version"])
        self.assertEqual(rc, 0)
        self.assertIn("0.1.0", out.getvalue())

    def test_doctor_json(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["doctor", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["product"], "claw-vm")
        self.assertIn("kvm", payload)
        self.assertTrue(payload["isolation"]["r2_vm_boundary"])

    def test_help_exit_2(self) -> None:
        with patch("sys.stdout", new=StringIO()):
            rc = main([])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
