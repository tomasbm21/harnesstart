from __future__ import annotations

import unittest

import _path  # noqa: F401
from claw_vm.computer import default_computer
from claw_vm.isolation import isolation_report
from claw_vm.kvm import kvm_report


class IsolationTest(unittest.TestCase):
    def test_qemu_is_vm_not_container(self) -> None:
        report = isolation_report(vmm="qemu", accel="tcg")
        self.assertTrue(report["r2_vm_boundary"])
        self.assertFalse(report["containers"])
        self.assertFalse(report["r2_hardware_kvm"])
        blob = " ".join(report["isolated"]).lower()  # type: ignore[arg-type]
        self.assertIn("guest kernel", blob)
        self.assertFalse(report["containers"])
        self.assertIn("not a container", str(report["boundary"]).lower())

    def test_firecracker_claims_kvm(self) -> None:
        report = isolation_report(vmm="firecracker", accel="kvm")
        self.assertTrue(report["r2_vm_boundary"])
        self.assertIn("Firecracker", report["boundary"])  # type: ignore[operator]

    def test_kvm_report_does_not_probe(self) -> None:
        report = kvm_report(probe_vcpu=False)
        self.assertIn("present", report)
        vcpu = report["vcpu"]
        self.assertIsInstance(vcpu, dict)
        # Must not require CREATE_VCPU on doctor.
        self.assertTrue(vcpu.get("skipped") or "ok" in vcpu)

    def test_default_computer_without_vcpu(self) -> None:
        c = default_computer()
        self.assertTrue(c.r2_isolated)
        info = c.doctor()
        self.assertTrue(info["r2_isolated"])


if __name__ == "__main__":
    unittest.main()
