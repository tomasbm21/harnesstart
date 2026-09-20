from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from norfront_claw.config import load_config
from norfront_claw.doctor import report, run_claw_vm_doctor


FAKE_CLAW_VM = r"""#!/usr/bin/env python3
import json
import sys

if "--probe-vcpu" in sys.argv:
    sys.stderr.write("refused --probe-vcpu\n")
    raise SystemExit(99)
json.dump(
    {
        "product": "claw-vm",
        "version": "0.0.1-test",
        "home": "/tmp/claw-vm-test",
        "kvm": {"present": True, "openable": True, "nested": True},
        "default_computer": {
            "name": "qemu",
            "r2_isolated": True,
            "vmm": "qemu",
            "accel": "tcg",
        },
        "isolation": {
            "r2_vm_boundary": True,
            "r2_hardware_kvm": False,
            "vmm": "qemu",
            "accel": "tcg",
            "boundary": "QEMU TCG test double",
        },
    },
    sys.stdout,
)
"""


class VmHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "BRIEF.md").write_text("brief\n", encoding="utf-8")
        (self.root / "product").mkdir()
        os.environ["CLAW_REPO"] = str(self.root)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_missing_claw_vm_is_not_an_error(self) -> None:
        cfg = load_config(self.root)
        payload = report(cfg)
        self.assertFalse(payload["r2_isolated"])
        self.assertFalse(payload["vm"]["present"])
        self.assertIn("r2-vm-computer", payload["stubbed"])
        ids = {c["id"]: c for c in payload["checks"]}
        self.assertIn("not present", ids["r2-vm"]["detail"])

    def test_doctor_calls_claw_vm_without_probe_vcpu(self) -> None:
        script = self.root / "product" / "vm" / "claw-vm"
        script.parent.mkdir()
        script.write_text(FAKE_CLAW_VM, encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        raw = run_claw_vm_doctor(self.root)
        self.assertIsNotNone(raw)
        self.assertTrue(raw["ok"])
        self.assertEqual(raw["default_computer"]["name"], "qemu")
        cfg = load_config(self.root)
        payload = report(cfg)
        self.assertTrue(payload["r2_isolated"])
        self.assertEqual(payload["vm"]["computer"], "qemu")
        self.assertEqual(payload["vm"]["accel"], "tcg")
        self.assertFalse(payload["vm"]["r2_hardware_kvm"])
        self.assertIn("r2-hardware-kvm", payload["stubbed"])
        self.assertNotIn("r2-vm-computer", payload["stubbed"])
        ids = {c["id"]: c for c in payload["checks"]}
        self.assertIn("never --probe-vcpu", ids["kvm"]["detail"])
        blob = json.dumps(payload)
        self.assertNotIn("--probe-vcpu", blob.replace("never --probe-vcpu", ""))


if __name__ == "__main__":
    unittest.main()
