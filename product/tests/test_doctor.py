from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_windows_host_is_ready(self) -> None:
        with (
            mock.patch("norfront_claw.doctor.platform.system", return_value="Windows"),
            mock.patch("norfront_claw.doctor.platform.release", return_value="10"),
            mock.patch("norfront_claw.doctor.platform.machine", return_value="AMD64"),
        ):
            payload = report(load_config(self.root))
        ids = {item["id"]: item for item in payload["checks"]}
        self.assertTrue(ids["linux"]["ok"])
        self.assertIn("Windows", ids["linux"]["detail"])
        self.assertEqual(payload["host"], "windows")
        self.assertTrue(payload["ready"])


if __name__ == "__main__":
    unittest.main()
