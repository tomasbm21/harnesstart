from __future__ import annotations

import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import _path  # noqa: F401
from claw_brains.base import BrainResult
from claw_brains.cli import main
from claw_brains.config import load_config
from claw_brains.registry import get_brain


class InstallTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "BRIEF.md").write_text("brief\n", encoding="utf-8")
        (self.root / "product").mkdir()
        os.environ.clear()
        os.environ.update(
            {
                "PATH": "/usr/bin:/bin",
                "HOME": str(self.root),
                "CLAW_REPO": str(self.root),
                "CLAW_BRAINS_HOME": str(self.root / "brains-home"),
                "CLAW_WORKSPACE": str(self.root / "work"),
            }
        )

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_prime_install_is_hint_not_download(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["install", "prime"])
        self.assertEqual(rc, 0)
        self.assertIn("product/claw", out.getvalue())
        self.assertIn("does not take Prime over", out.getvalue())

    def test_goose_install_calls_official_url(self) -> None:
        seen: dict = {}

        def fake_curl(url, **kwargs):
            seen["url"] = url
            seen["env"] = kwargs.get("extra_env")
            return BrainResult(ok=True, returncode=0, stdout="installed\n", stderr="")

        with patch("claw_brains.backends.goose.curl_pipe_sh", side_effect=fake_curl):
            with patch("sys.stdout", new=StringIO()) as out:
                rc = main(["install", "goose"])
        self.assertEqual(rc, 0)
        self.assertIn("github.com/aaif-goose/goose", seen["url"])
        self.assertEqual(seen["env"]["CONFIGURE"], "false")
        self.assertIn("installed", out.getvalue())

    def test_openclaw_install_is_noninteractive(self) -> None:
        seen: dict = {}

        def fake_curl(url, **kwargs):
            seen["url"] = url
            seen["env"] = kwargs.get("extra_env")
            return BrainResult(ok=True, returncode=0, stdout="ok\n", stderr="")

        with patch("claw_brains.backends.openclaw.curl_pipe_sh", side_effect=fake_curl):
            rc = main(["install", "openclaw"])
        self.assertEqual(rc, 0)
        self.assertEqual(seen["env"]["OPENCLAW_NO_ONBOARD"], "1")
        self.assertEqual(seen["env"]["OPENCLAW_NO_PROMPT"], "1")
        self.assertIn("openclaw.ai/install.sh", seen["url"])

    def test_openhands_install_url(self) -> None:
        seen: dict = {}

        def fake_curl(url, **kwargs):
            seen["url"] = url
            return BrainResult(ok=True, returncode=0, stdout="ok\n", stderr="")

        cfg = load_config(self.root)
        with patch("claw_brains.backends.openhands.curl_pipe_sh", side_effect=fake_curl):
            result = get_brain("openhands", cfg).install()
        self.assertTrue(result.ok)
        self.assertIn("install.openhands.dev", seen["url"])


if __name__ == "__main__":
    unittest.main()
