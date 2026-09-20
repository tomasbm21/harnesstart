from __future__ import annotations

import json
import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import _path  # noqa: F401
from claw_brains.cli import main
from claw_brains.config import load_config
from claw_brains.secrets import redact


class SecretsTest(unittest.TestCase):
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

    def test_doctor_does_not_print_key_value(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "leaked-if-printed-secret"
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["doctor", "--json"])
        self.assertEqual(rc, 0)
        text = out.getvalue()
        self.assertNotIn("leaked-if-printed-secret", text)
        payload = json.loads(text)
        self.assertEqual(payload["keys"]["DEEPSEEK_API_KEY"], "set")
        blob = json.dumps(payload)
        self.assertNotIn("leaked-if-printed-secret", blob)

    def test_config_repr_hides_values(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "leaked-if-printed-secret"
        cfg = load_config(self.root)
        self.assertIn("deepseek_key=set", repr(cfg))
        self.assertNotIn("leaked-if-printed-secret", repr(cfg))

    def test_redact(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "leaked-if-printed-secret"
        self.assertEqual(redact("pre leaked-if-printed-secret post"), "pre *** post")

    def test_env_file_loaded_without_override(self) -> None:
        claw = self.root / "claw.env"
        claw.write_text("DEEPSEEK_API_KEY=from-file-secret-value\n", encoding="utf-8")
        os.environ.pop("DEEPSEEK_API_KEY", None)
        cfg = load_config(self.root)
        self.assertTrue(cfg.deepseek_key)
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["doctor", "--json"])
        self.assertEqual(rc, 0)
        self.assertNotIn("from-file-secret-value", out.getvalue())


if __name__ == "__main__":
    unittest.main()
