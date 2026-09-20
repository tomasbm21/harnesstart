from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
from claw_vm.paths import check_name, vm_home


class NameTest(unittest.TestCase):
    def test_ok(self) -> None:
        self.assertEqual(check_name("agent"), "agent")
        self.assertEqual(check_name("a1-b"), "a1-b")

    def test_bad(self) -> None:
        with self.assertRaises(ValueError):
            check_name("Agent")
        with self.assertRaises(ValueError):
            check_name("1agent")
        with self.assertRaises(ValueError):
            check_name("")


class HomeTest(unittest.TestCase):
    def test_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            os.environ["CLAW_VM_HOME"] = td
            try:
                self.assertEqual(vm_home(), Path(td).resolve())
            finally:
                os.environ.pop("CLAW_VM_HOME", None)


if __name__ == "__main__":
    unittest.main()
