"""Live guest boot. Skipped unless CLAW_VM_LIVE=1."""

from __future__ import annotations

import os
import tempfile
import unittest

import _path  # noqa: F401
from claw_vm.instance import destroy, exec_in, persist_probe, start, stop


@unittest.skipUnless(os.environ.get("CLAW_VM_LIVE") == "1", "set CLAW_VM_LIVE=1")
class LiveVmTest(unittest.TestCase):
    def test_start_uname_and_host_not_visible(self) -> None:
        home = tempfile.mkdtemp(prefix="claw-vm-live-")
        os.environ["CLAW_VM_HOME"] = home
        name = "livetest"
        try:
            vm = start(name, image=os.environ.get("CLAW_VM_IMAGE", "cirros"), vmm="qemu", timeout=240)
            uname = vm.exec("uname -s")
            self.assertEqual(uname.returncode, 0, uname.stderr)
            self.assertIn("Linux", uname.stdout)
            # Host repo must not be visible inside the guest.
            probe = exec_in(name, "test -e /workspace/BRIEF.md; echo $?")
            self.assertEqual(probe.stdout.strip(), "1")
            iso = vm.isolation()
            self.assertTrue(iso["r2_vm_boundary"])
            self.assertFalse(iso["containers"])
            persisted = persist_probe(name)
            self.assertTrue(persisted["ok"], persisted)
        finally:
            try:
                destroy(name)
            except Exception:
                stop(name)
            os.environ.pop("CLAW_VM_HOME", None)


if __name__ == "__main__":
    unittest.main()
