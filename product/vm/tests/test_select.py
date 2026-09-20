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
from claw_vm.names import UnknownBackend
from claw_vm.registry import select, selected_id, selected_source
from claw_vm.computer import default_computer


class SelectTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "vm-home"
        os.environ["CLAW_VM_HOME"] = str(self.home)
        os.environ.pop("CLAW_VM_BACKEND", None)
        os.environ.pop("CLAW_VM_VMM", None)
        os.environ.pop("CLAW_VM_PROBE_VCPU", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_default_is_qemu(self) -> None:
        self.assertEqual(selected_id(), "qemu")
        self.assertEqual(selected_source()[1], "default")
        self.assertEqual(default_computer().name, "qemu")

    def test_qemu_stays_default_even_if_kvm_ok(self) -> None:
        with patch("claw_vm.registry.vcpu_known_good", return_value=True):
            self.assertEqual(selected_id(), "qemu")
            self.assertEqual(default_computer().name, "qemu")

    def test_select_persists_celesto(self) -> None:
        self.assertEqual(select("celesto"), "celesto")
        self.assertEqual(selected_id(), "celesto")
        self.assertEqual(selected_source()[1], "file")
        self.assertEqual((self.home / "selected").read_text(encoding="utf-8").strip(), "celesto")
        self.assertEqual(default_computer().name, "celesto")

    def test_env_wins_over_file(self) -> None:
        select("celesto")
        os.environ["CLAW_VM_BACKEND"] = "libkrun"
        self.assertEqual(selected_id(), "libkrun")
        self.assertEqual(selected_source()[1], "env")

    def test_vmm_env_is_alias_when_backend_unset(self) -> None:
        os.environ["CLAW_VM_VMM"] = "firecracker"
        self.assertEqual(selected_id(), "firecracker")
        self.assertEqual(selected_source()[1], "env")

    def test_backend_env_wins_over_vmm_env(self) -> None:
        os.environ["CLAW_VM_VMM"] = "firecracker"
        os.environ["CLAW_VM_BACKEND"] = "agentenv"
        self.assertEqual(selected_id(), "agentenv")

    def test_cli_select_json(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["select", "e2b", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["selected"], "e2b")
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["selected", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["id"], "e2b")
        self.assertEqual(payload["source"], "file")
        self.assertEqual(payload["default"], "qemu")

    def test_aliases(self) -> None:
        self.assertEqual(select("msb"), "microsandbox")
        self.assertEqual(select("aenv"), "agentenv")
        self.assertEqual(select("smolvm"), "celesto")
        self.assertEqual(select("krun"), "libkrun")
        self.assertEqual(select("fc"), "firecracker")

    def test_unknown_backend(self) -> None:
        with self.assertRaises(UnknownBackend):
            select("docker")
        with patch("sys.stderr", new=StringIO()) as err:
            rc = main(["select", "hermes"])
        self.assertEqual(rc, 2)
        self.assertIn("unknown backend", err.getvalue())


if __name__ == "__main__":
    unittest.main()
