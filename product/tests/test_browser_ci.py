"""Offline Jev path: stub adapter, no TypeSafe, bounded time.

Live choose/browse is opt-in via CLAW_BROWSER_LIVE=1 and is not part of this
suite. See the operator console notes for the full split.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from norfront_claw.browser import live_browser_opt_in

PRODUCT = Path(__file__).resolve().parent.parent
REPO = PRODUCT.parent


class BrowserCiTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)

    def test_live_opt_in_is_exact_flag(self) -> None:
        os.environ.pop("CLAW_BROWSER_LIVE", None)
        self.assertFalse(live_browser_opt_in())
        os.environ["CLAW_BROWSER_LIVE"] = "true"
        self.assertFalse(live_browser_opt_in())
        os.environ["CLAW_BROWSER_LIVE"] = "1"
        self.assertTrue(live_browser_opt_in())

    def test_stub_observe_and_guards_finish_without_typesafe(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="claw-browser-ci-"))
        (root / "BRIEF.md").write_text("brief\n", encoding="utf-8")
        (root / "product").mkdir()
        env = os.environ.copy()
        for key in (
            "DEEPSEEK_API_KEY",
            "TYPESAFE_API_KEY",
            "TEXT_MODEL_API_KEY",
            "CLAW_BROWSER_LIVE",
        ):
            env.pop(key, None)
        env["CLAW_NO_KEY_PROMPT"] = "1"
        env["CLAW_BROWSER_ADAPTER"] = "fake_adapter:create_adapter"
        env["PYTHONPATH"] = str(PRODUCT) + os.pathsep + str(PRODUCT / "tests")
        for command in (
            ["observe", "https://example.com", "--json"],
            ["guards", "--json"],
        ):
            try:
                proc = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "norfront_claw",
                        "--no-prompt",
                        "--repo",
                        str(root),
                        *command,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    cwd=str(REPO),
                    env=env,
                    timeout=8,
                )
            except subprocess.TimeoutExpired:
                self.fail(f"{command[0]} exceeded 8s on the stub adapter")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["used_typesafe"])
            self.assertTrue(payload["ok"])
            self.assertNotIn("TYPESAFE_API_KEY=", proc.stdout)
            self.assertNotIn("TYPESAFE_API_KEY=", proc.stderr)
