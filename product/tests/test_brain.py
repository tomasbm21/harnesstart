from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from subprocess import CompletedProcess

from norfront_claw.brain import PrimeBrain, install_prime_agent
from norfront_claw.config import load_config


def subprocess_ok(argv, stdout: str = "") -> CompletedProcess[str]:
    return CompletedProcess(argv, 0, stdout=stdout, stderr="")


class BrainTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "BRIEF.md").write_text("brief\n", encoding="utf-8")
        product = self.root / "product"
        product.mkdir()
        (product / "prime-prompt.md").write_text("claw-brain-prompt\n", encoding="utf-8")
        fake = self.root / "bin"
        fake.mkdir()
        self.binary = fake / "prime-agent"
        self.binary.write_text("#!/bin/sh\necho prime-agent 0.0.0-test\n", encoding="utf-8")
        self.binary.chmod(self.binary.stat().st_mode | stat.S_IEXEC)
        os.environ["CLAW_REPO"] = str(self.root)
        os.environ["CLAW_PRIME_BIN"] = str(self.binary)
        os.environ["CLAW_WORKSPACE"] = str(self.root / "work")
        os.environ.pop("DEEPSEEK_API_KEY", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_argv_has_no_api_key_flag(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "should-not-appear-on-argv"
        cfg = load_config(self.root)
        argv = PrimeBrain(cfg).print_argv("ping")
        joined = " ".join(argv)
        self.assertNotIn("--api-key", argv)
        self.assertNotIn("should-not-appear-on-argv", joined)
        self.assertIn("--provider", argv)
        self.assertIn("deepseek", argv)
        self.assertIn("--no-context-files", argv)
        self.assertIn("claw-brain-prompt", joined)

    def test_install_timeout_is_one_budget(self) -> None:
        seen: list[float] = []

        def fake_run(argv, **kwargs):
            seen.append(float(kwargs["timeout"]))
            if argv[:1] == ["sh"]:
                return subprocess_ok(argv)
            return subprocess_ok(argv, stdout="echo ok\n")

        with patch("norfront_claw.brain.shutil.which", return_value="/usr/bin/curl"):
            with patch("norfront_claw.brain.subprocess.run", side_effect=fake_run):
                install_prime_agent(timeout=20)
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(item <= 20 for item in seen))

    def test_run_without_key_fails_before_exec(self) -> None:
        cfg = load_config(self.root)
        with self.assertRaises(Exception) as ctx:
            PrimeBrain(cfg).run_print("ping")
        self.assertIn("DEEPSEEK_API_KEY", str(ctx.exception))
        self.assertNotIn("should-not", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
