from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
from claw_brains.base import which_binary
from claw_brains.install import promote_to_local_bin
from claw_brains.paths import nvm_bin_dirs


class WhichTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ["HOME"] = str(self.root)
        os.environ["NVM_DIR"] = str(self.root / ".nvm")
        os.environ["PATH"] = "/usr/bin:/bin"

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_finds_nvm_global_binary(self) -> None:
        nvm_bin = self.root / ".nvm" / "versions" / "node" / "v26.9.0" / "bin"
        nvm_bin.mkdir(parents=True)
        binary = nvm_bin / "openclaw"
        binary.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
        binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
        dirs = nvm_bin_dirs()
        self.assertTrue(dirs)
        found = which_binary("openclaw", ("openclaw",))
        self.assertEqual(found, str(binary))

    def test_promote_symlink(self) -> None:
        src_dir = self.root / "somewhere"
        src_dir.mkdir()
        src = src_dir / "openclaw"
        src.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
        src.chmod(src.stat().st_mode | stat.S_IEXEC)
        linked = promote_to_local_bin("openclaw", str(src))
        self.assertIsNotNone(linked)
        path = Path(linked)
        self.assertTrue(path.exists())
        self.assertEqual(path.resolve(), src.resolve())


if __name__ == "__main__":
    unittest.main()
