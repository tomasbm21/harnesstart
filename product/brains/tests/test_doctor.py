from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import _path  # noqa: F401
from claw_brains.cli import main
from claw_brains.config import load_config
from claw_brains.doctor import doctor_payload


class DoctorTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "BRIEF.md").write_text("brief\n", encoding="utf-8")
        (self.root / "product").mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        os.environ.clear()
        os.environ.update(
            {
                "PATH": str(self.bin) + os.pathsep + self._old.get("PATH", "/usr/bin"),
                "HOME": self._old.get("HOME", str(self.root)),
                "CLAW_REPO": str(self.root),
                "CLAW_BRAINS_HOME": str(self.root / "brains-home"),
                "CLAW_WORKSPACE": str(self.root / "work"),
            }
        )
        for key in ("DEEPSEEK_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY", "CLAW_BRAIN"):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def _fake(self, name: str, version: str) -> Path:
        path = self.bin / name
        path.write_text(f"#!/bin/sh\necho {version}\n", encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return path

    def test_missing_brains_are_warnings_not_hard_fail(self) -> None:
        cfg = load_config(self.root)
        payload = doctor_payload(cfg)
        self.assertTrue(payload["ok"])
        by_id = {b["id"]: b for b in payload["brains"]}
        self.assertFalse(by_id["goose"]["present"])
        self.assertEqual(by_id["goose"]["live_turn"], "not-installed")
        self.assertEqual(by_id["prime"]["role"], "default")
        self.assertEqual(by_id["openhands"]["role"], "optional")

    def test_fake_goose_present(self) -> None:
        self._fake("goose", "goose 9.9.9-test")
        cfg = load_config(self.root)
        payload = doctor_payload(cfg, brain="goose")
        report = payload["brains"][0]
        self.assertTrue(report["present"])
        self.assertIn("9.9.9-test", report["version"] or "")
        self.assertEqual(report["live_turn"], "stubbed-no-key")

    def test_doctor_one_brain_cli(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["doctor", "openhands", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual([b["id"] for b in payload["brains"]], ["openhands"])


if __name__ == "__main__":
    unittest.main()
