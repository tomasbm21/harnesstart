from __future__ import annotations

import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import _path  # noqa: F401
from claw_vm.backends import SKIP_NO_DOCKER, SKIP_NO_KVM, StartSkipped, live_start_for
from claw_vm.cli import main
from claw_vm.instance import start
from claw_vm.names import KNOWN_BACKENDS


OPTIONAL = ("celesto", "e2b", "agentenv", "microsandbox", "libkrun", "firecracker")


class SkipStartTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CLAW_VM_HOME"] = str(Path(self.tmp.name) / "vm-home")
        os.environ.pop("CLAW_VM_BACKEND", None)
        os.environ.pop("CLAW_VM_VMM", None)
        os.environ.pop("CLAW_VM_PROBE_VCPU", None)
        os.environ.pop("CLAW_VM_FORCE_FIRECRACKER", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_optional_backends_skip_without_working_kvm(self) -> None:
        with patch("claw_vm.backends._run_optional") as run_opt:
            for bid in OPTIONAL:
                with self.assertRaises(StartSkipped) as cm:
                    start("agent", backend=bid)
                self.assertIn(cm.exception.reason, {SKIP_NO_KVM, SKIP_NO_DOCKER, "skipped-not-installed", "skipped-no-cli"})
                self.assertFalse(cm.exception.payload()["started"])
            run_opt.assert_not_called()

    def test_e2b_records_docker_and_kvm_skips(self) -> None:
        live = live_start_for("e2b")
        self.assertFalse(live.ready)
        self.assertTrue({SKIP_NO_KVM, SKIP_NO_DOCKER} & set(live.skip_reasons) or live.reason != "ready")

    def test_cli_start_celesto_exits_2(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["start", "agent", "--backend", "celesto", "--json"])
        self.assertEqual(rc, 2)
        payload = __import__("json").loads(out.getvalue())
        self.assertTrue(payload["skipped"])
        self.assertEqual(payload["backend"], "celesto")
        self.assertFalse(payload["started"])

    def test_cli_start_each_optional(self) -> None:
        for bid in ("celesto", "e2b", "agentenv", "microsandbox", "libkrun"):
            with patch("sys.stdout", new=StringIO()) as out:
                rc = main(["start", "--backend", bid, "--json"])
            self.assertEqual(rc, 2, bid)
            payload = __import__("json").loads(out.getvalue())
            self.assertTrue(payload["skipped"], bid)
            self.assertEqual(payload["backend"], bid)

    def test_doctor_each_backend_flag(self) -> None:
        for bid in KNOWN_BACKENDS:
            with patch("sys.stdout", new=StringIO()) as out:
                rc = main(["doctor", "--backend", bid, "--json"])
            self.assertEqual(rc, 0, bid)
            payload = __import__("json").loads(out.getvalue())
            self.assertEqual(len(payload["backends"]), 1, bid)
            self.assertEqual(payload["backends"][0]["name"], bid)


if __name__ == "__main__":
    unittest.main()
