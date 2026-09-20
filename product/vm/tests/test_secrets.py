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
from claw_vm.kvm import probe_kvm_vcpu


SECRET = "celesto-super-secret-value-9f3a"
E2B_SECRET = "e2b-super-secret-value-1c4d"


class SecretsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CLAW_VM_HOME"] = str(Path(self.tmp.name) / "vm-home")
        os.environ["CELESTO_API_KEY"] = SECRET
        os.environ["E2B_API_KEY"] = E2B_SECRET
        os.environ.pop("CLAW_VM_BACKEND", None)
        os.environ.pop("CLAW_VM_VMM", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_doctor_does_not_print_keys(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["doctor", "--json"])
        self.assertEqual(rc, 0)
        blob = out.getvalue()
        self.assertNotIn(SECRET, blob)
        self.assertNotIn(E2B_SECRET, blob)
        payload = json.loads(blob)
        celesto = next(b for b in payload["backends"] if b["name"] == "celesto")
        self.assertEqual(celesto["keys"]["CELESTO_API_KEY"], "set")

    def test_start_skip_does_not_print_keys(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["start", "--backend", "celesto", "--json"])
        self.assertEqual(rc, 2)
        blob = out.getvalue()
        self.assertNotIn(SECRET, blob)
        self.assertNotIn(E2B_SECRET, blob)

    def test_doctor_does_not_probe_vcpu(self) -> None:
        with patch("claw_vm.kvm.probe_kvm_vcpu", wraps=probe_kvm_vcpu) as probe:
            with patch("sys.stdout", new=StringIO()):
                rc = main(["doctor", "--json"])
            self.assertEqual(rc, 0)
            probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
