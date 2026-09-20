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
from claw_brains.backends.goose import GooseBrain
from claw_brains.backends.openclaw import OpenClawBrain
from claw_brains.backends.openhands import OpenHandsBrain
from claw_brains.backends.prime import PrimeBrain
from claw_brains.base import BrainError
from claw_brains.cli import main
from claw_brains.config import load_config


class RunTest(unittest.TestCase):
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
                "PATH": str(self.bin) + os.pathsep + "/usr/bin:/bin",
                "HOME": str(self.root),
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

    def _fake(self, name: str) -> Path:
        path = self.bin / name
        path.write_text("#!/bin/sh\necho pong-from-stub\n", encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return path

    def test_run_without_key_is_stub_no_exec(self) -> None:
        fake = self._fake("goose")
        os.environ["CLAW_GOOSE_BIN"] = str(fake)
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["run", "--brain", "goose", "Reply with pong"])
        self.assertEqual(rc, 2)
        self.assertIn("stubbed", out.getvalue())
        self.assertIn("claw.env", out.getvalue())
        self.assertNotIn("pong-from-stub", out.getvalue())

    def test_openhands_argv_has_no_api_key_flag(self) -> None:
        fake = self._fake("openhands")
        os.environ["CLAW_OPENHANDS_BIN"] = str(fake)
        os.environ["DEEPSEEK_API_KEY"] = "should-not-appear-on-argv"
        cfg = load_config(self.root)
        argv = OpenHandsBrain(cfg).print_argv("ping")
        joined = " ".join(argv)
        self.assertNotIn("--api-key", argv)
        self.assertNotIn("should-not-appear-on-argv", joined)
        self.assertIn("--headless", argv)
        self.assertIn("--override-with-envs", argv)

    def test_openclaw_argv_auth_env_only(self) -> None:
        fake = self._fake("openclaw")
        os.environ["CLAW_OPENCLAW_BIN"] = str(fake)
        os.environ["DEEPSEEK_API_KEY"] = "should-not-appear-on-argv"
        cfg = load_config(self.root)
        argv = OpenClawBrain(cfg).print_argv("ping")
        joined = " ".join(argv)
        self.assertIn("agent", argv)
        self.assertIn("exec", argv)
        self.assertIn("--auth-env-only", argv)
        self.assertNotIn("should-not-appear-on-argv", joined)
        self.assertNotIn("--api-key", argv)

    def test_goose_argv(self) -> None:
        fake = self._fake("goose")
        os.environ["CLAW_GOOSE_BIN"] = str(fake)
        os.environ["DEEPSEEK_API_KEY"] = "should-not-appear-on-argv"
        cfg = load_config(self.root)
        argv = GooseBrain(cfg).print_argv("ping")
        self.assertIn("run", argv)
        self.assertIn("--no-session", argv)
        self.assertNotIn("should-not-appear-on-argv", " ".join(argv))

    def test_prime_argv(self) -> None:
        fake = self._fake("prime-agent")
        os.environ["CLAW_PRIME_BIN"] = str(fake)
        os.environ["DEEPSEEK_API_KEY"] = "should-not-appear-on-argv"
        cfg = load_config(self.root)
        argv = PrimeBrain(cfg).print_argv("ping")
        self.assertIn("-p", argv)
        self.assertIn("--no-context-files", argv)
        self.assertNotIn("--api-key", argv)
        self.assertNotIn("should-not-appear-on-argv", " ".join(argv))

    def test_refuse_api_key_flag(self) -> None:
        from claw_brains.base import refuse_secret_flags

        with self.assertRaises(BrainError):
            refuse_secret_flags(["openhands", "--api-key", "nope"])

    def test_run_with_key_execs_fake_binary(self) -> None:
        fake = self._fake("goose")
        os.environ["CLAW_GOOSE_BIN"] = str(fake)
        os.environ["DEEPSEEK_API_KEY"] = "present-but-must-not-print"
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["run", "--brain", "goose", "--json", "ping"])
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["ok"])
        self.assertIn("pong-from-stub", payload["stdout"])
        self.assertNotIn("present-but-must-not-print", out.getvalue())
        self.assertNotIn("--api-key", payload["argv"])


if __name__ == "__main__":
    unittest.main()
