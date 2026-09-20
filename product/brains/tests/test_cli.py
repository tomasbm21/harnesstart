from __future__ import annotations

import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import _path  # noqa: F401
from claw_brains.cli import main


class CliTest(unittest.TestCase):
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
        for key in (
            "DEEPSEEK_API_KEY",
            "LLM_API_KEY",
            "OPENAI_API_KEY",
            "CLAW_BRAIN",
        ):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_version(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["--version"])
        self.assertEqual(rc, 0)
        self.assertIn("0.1.0", out.getvalue())

    def test_help_exit_2(self) -> None:
        with patch("sys.stdout", new=StringIO()):
            rc = main([])
        self.assertEqual(rc, 2)

    def test_doctor_json_default_prime(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["doctor", "--json"])
        self.assertEqual(rc, 0)
        import json

        payload = json.loads(out.getvalue())
        self.assertEqual(payload["product"], "claw-brains")
        self.assertEqual(payload["default"], "prime")
        self.assertEqual(payload["selected"], "prime")
        ids = [b["id"] for b in payload["brains"]]
        self.assertEqual(ids, ["prime", "openhands", "openclaw", "goose"])
        self.assertEqual(payload["keys"]["DEEPSEEK_API_KEY"], "missing")

    def test_unknown_brain_exit_2(self) -> None:
        with patch("sys.stdout", new=StringIO()), patch("sys.stderr", new=StringIO()) as err:
            rc = main(["select", "hermes"])
        self.assertEqual(rc, 2)
        self.assertIn("unknown brain", err.getvalue())


if __name__ == "__main__":
    unittest.main()
