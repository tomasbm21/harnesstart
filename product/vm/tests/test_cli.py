from __future__ import annotations

import json
import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import _path  # noqa: F401
from claw_vm.cli import main


class CliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CLAW_VM_HOME"] = str(Path(self.tmp.name) / "vm-home")
        os.environ.pop("CLAW_VM_BACKEND", None)
        os.environ.pop("CLAW_VM_VMM", None)
        os.environ.pop("CLAW_VM_PROBE_VCPU", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_version(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["--version"])
        self.assertEqual(rc, 0)
        self.assertIn("0.2.0", out.getvalue())

    def test_doctor_json(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["doctor", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["product"], "claw-vm")
        self.assertIn("kvm", payload)
        self.assertTrue(payload["isolation"]["r2_vm_boundary"])
        self.assertEqual(payload["default"], "qemu")
        self.assertEqual(payload["selected"], "qemu")
        names = [b["name"] for b in payload["backends"]]
        self.assertEqual(
            names,
            ["qemu", "firecracker", "celesto", "e2b", "agentenv", "microsandbox", "libkrun"],
        )
        self.assertIn("docker", payload)
        self.assertTrue(payload["kvm"]["vcpu"].get("skipped") or "ok" in payload["kvm"]["vcpu"])

    def test_help_exit_2(self) -> None:
        with patch("sys.stdout", new=StringIO()):
            rc = main([])
        self.assertEqual(rc, 2)

    def test_list_marks_qemu_default(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["list", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["selected"], "qemu")
        self.assertEqual(payload["default"], "qemu")
        qemu = next(b for b in payload["backends"] if b["name"] == "qemu")
        self.assertTrue(qemu["selected"])


if __name__ == "__main__":
    unittest.main()
