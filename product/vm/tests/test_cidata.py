from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
from claw_vm.priv import have
from claw_vm.seed import write_cidata_iso


class CidataImageTest(unittest.TestCase):
    @unittest.skipUnless(have("mkfs.vfat") and have("mcopy"), "need dosfstools/mtools")
    def test_vfat_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "cidata.img"
            write_cidata_iso(
                dest,
                hostname="agent",
                ssh_pub="ssh-ed25519 AAAA test",
                image_id="cirros",
            )
            import os
            import subprocess

            listing = subprocess.check_output(
                ["mdir", "-i", str(dest)],
                env={**os.environ, "MTOOLS_SKIP_CHECK": "1"},
                text=True,
            )
            self.assertIn("user-data", listing)
            self.assertIn("meta-data", listing)
            self.assertNotIn("USER_DAT", listing)
