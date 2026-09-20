from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from norfront_claw.config import load_config
from norfront_claw.doctor import report


class DoctorTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "BRIEF.md").write_text("brief\n", encoding="utf-8")
        (self.root / "product").mkdir()
        os.environ["CLAW_REPO"] = str(self.root)
        os.environ.pop("TYPESAFE_API_KEY", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_report_marks_typesafe_optional(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "report-must-not-echo-this-value"
        cfg = load_config(self.root)
        payload = report(cfg)
        blob = json.dumps(payload)
        self.assertNotIn("report-must-not-echo-this-value", blob)
        self.assertEqual(payload["keys"]["TYPESAFE_API_KEY"], "missing")
        self.assertFalse(payload["r2_isolated"])
        self.assertEqual(payload["adapter"], "missing-jev")


if __name__ == "__main__":
    unittest.main()
