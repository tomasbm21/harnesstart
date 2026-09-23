from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from norfront_claw.browser import _drop_claw_jev_modules
from norfront_claw.cli import main
from norfront_claw.config import load_config, parse_env_file
from norfront_claw.prompt_keys import (
    ensure_boot_keys,
    format_assignment,
    keys_for_command,
    should_prompt,
    upsert_claw_env,
)

SECRET = "tty-prompt-secret-value-7f4c"
SAFE = "sk-testkey_abc123"

_JEV_STUB = '''
import os

class PolicyUnavailable(RuntimeError):
    pass

class ClawJev:
    def observe(self, url, *, screenshot=False):
        return {"url": url, "title": "Example Domain", "actions": [{"id": 1, "kind": "wait"}]}
    def close(self):
        return None

def observe(url, *, screenshot=False):
    return ClawJev().observe(url, screenshot=screenshot)

def check_guards():
    return {"ok": True, "passed": 1, "checks": ["stub"], "typesafe_required": False}

def choose(page, goal, history=None):
    if not os.environ.get("TYPESAFE_API_KEY", "").strip():
        raise PolicyUnavailable(
            "Live Jev choose()/run() need TYPESAFE_API_KEY in the environment (not chat)."
        )
    return {"operation": "WAIT", "goal": goal}

def run(url, goal, **kwargs):
    choose({}, goal)
    yield {"url": url, "goal": goal}

def policy_status():
    present = bool(os.environ.get("TYPESAFE_API_KEY", "").strip())
    return {"choose": present, "type_text": False, "observe_needs_key": False, "guards_need_key": False}

def doctor():
    return {"ok": True}
'''


def _write_jev_stub(root: Path) -> None:
    pkg = root / "product" / "jev" / "claw_jev"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text(_JEV_STUB, encoding="utf-8")


class PromptKeysTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "BRIEF.md").write_text("brief\n", encoding="utf-8")
        (self.root / "product").mkdir()
        os.environ.clear()
        os.environ.update(
            {
                "PATH": self._old.get("PATH", "/usr/bin:/bin"),
                "HOME": str(self.root),
                "CLAW_REPO": str(self.root),
                "CLAW_WORKSPACE": str(self.root / "work"),
            }
        )
        os.environ.pop("DEEPSEEK_API_KEY", None)
        os.environ.pop("TYPESAFE_API_KEY", None)
        os.environ.pop("CLAW_NO_KEY_PROMPT", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_keys_for_commands(self) -> None:
        self.assertEqual(
            keys_for_command("doctor"),
            (("DEEPSEEK_API_KEY", False), ("TYPESAFE_API_KEY", True)),
        )
        self.assertEqual(keys_for_command("run"), (("DEEPSEEK_API_KEY", False),))
        self.assertEqual(keys_for_command("choose"), (("TYPESAFE_API_KEY", False),))
        self.assertEqual(keys_for_command("browse"), (("TYPESAFE_API_KEY", False),))
        self.assertEqual(keys_for_command("observe"), ())
        self.assertEqual(keys_for_command("guards"), ())
        self.assertEqual(keys_for_command("test"), ())

    def test_non_tty_does_not_prompt(self) -> None:
        with patch("norfront_claw.prompt_keys.stdin_is_tty", return_value=False):
            with patch("norfront_claw.prompt_keys._read_secret") as read:
                cfg = load_config(self.root)
                out = ensure_boot_keys(cfg, command="doctor")
                read.assert_not_called()
                self.assertFalse(out.deepseek_key)
                self.assertFalse((self.root / "claw.env").exists())

    def test_no_prompt_flag_and_env_skip(self) -> None:
        with patch("norfront_claw.prompt_keys._stdio_can_prompt", return_value=True):
            with patch("norfront_claw.prompt_keys.stdin_is_tty", return_value=True):
                with patch("norfront_claw.prompt_keys._read_secret") as read:
                    cfg = load_config(self.root)
                    ensure_boot_keys(cfg, command="doctor", no_prompt=True)
                    read.assert_not_called()
                    os.environ["CLAW_NO_KEY_PROMPT"] = "1"
                    ensure_boot_keys(cfg, command="run")
                    read.assert_not_called()

    def test_tty_doctor_saves_deepseek_not_printed(self) -> None:
        with patch("norfront_claw.prompt_keys._stdio_can_prompt", return_value=True):
            with patch("norfront_claw.prompt_keys.stdin_is_tty", return_value=True):
                with patch(
                    "norfront_claw.prompt_keys._read_secret",
                    side_effect=[SAFE, ""],
                ):
                    with patch("sys.stdout", new=StringIO()) as out:
                        with patch("sys.stderr", new=StringIO()) as err:
                            rc = main(["--repo", str(self.root), "doctor", "--json"])
        self.assertEqual(rc, 0)
        blob = out.getvalue() + err.getvalue()
        self.assertNotIn(SAFE, blob)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["keys"]["DEEPSEEK_API_KEY"], "set")
        self.assertEqual(payload["keys"]["TYPESAFE_API_KEY"], "missing")
        parsed = parse_env_file(self.root / "claw.env")
        self.assertEqual(parsed["DEEPSEEK_API_KEY"], SAFE)
        mode = (self.root / "claw.env").stat().st_mode
        self.assertEqual(stat.S_IMODE(mode), 0o600)

    def test_tty_doctor_typesafe_enter_skips(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "already-set-from-env-aaaa"
        with patch("norfront_claw.prompt_keys._stdio_can_prompt", return_value=True):
            with patch(
                "norfront_claw.prompt_keys._read_secret",
                return_value="   ",
            ) as read:
                cfg = ensure_boot_keys(load_config(self.root), command="doctor")
                read.assert_called_once()
                self.assertFalse(cfg.typesafe_key)
                self.assertFalse((self.root / "claw.env").exists())

    def test_upsert_replaces_empty_and_hermes_placeholder(self) -> None:
        path = self.root / "claw.env"
        path.write_text(
            "CLAW_MODEL=deepseek-v4-pro\nDEEPSEEK_API_KEY=\nWEB_BACKEND=\n",
            encoding="utf-8",
        )
        upsert_claw_env(path, "DEEPSEEK_API_KEY", SAFE)
        text = path.read_text(encoding="utf-8")
        self.assertIn(f"DEEPSEEK_API_KEY={SAFE}", text)
        self.assertIn("CLAW_MODEL=deepseek-v4-pro", text)
        self.assertEqual(text.count("DEEPSEEK_API_KEY="), 1)
        path.write_text("DEEPSEEK_API_KEY=__stored_in_hermes__\n", encoding="utf-8")
        upsert_claw_env(path, "DEEPSEEK_API_KEY", SAFE)
        self.assertEqual(parse_env_file(path)["DEEPSEEK_API_KEY"], SAFE)

    def test_format_assignment_quotes_specials_roundtrip(self) -> None:
        self.assertEqual(format_assignment("DEEPSEEK_API_KEY", SAFE), f"DEEPSEEK_API_KEY={SAFE}")
        raw = "abc def+ghi"
        line = format_assignment("DEEPSEEK_API_KEY", raw)
        self.assertTrue(line.startswith('DEEPSEEK_API_KEY="'))
        path = self.root / "t.env"
        path.write_text(line + "\n", encoding="utf-8")
        self.assertEqual(parse_env_file(path)["DEEPSEEK_API_KEY"], raw)
        with self.assertRaises(ValueError):
            format_assignment("DEEPSEEK_API_KEY", 'abc "def" ghi')

    def test_cli_has_no_api_key_flag(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main([])
        text = out.getvalue()
        self.assertEqual(rc, 0)
        self.assertEqual(len(text.splitlines()), 5)
        self.assertNotIn("--api-key", text.lower())
        self.assertNotIn("--apikey", text.lower())

    def test_should_prompt_false_without_tty(self) -> None:
        with patch("norfront_claw.prompt_keys.stdin_is_tty", return_value=False):
            self.assertFalse(should_prompt())

    def test_piped_capture_does_not_prompt_even_if_stdin_tty(self) -> None:
        with patch("norfront_claw.prompt_keys.stdin_is_tty", return_value=True):
            with patch.object(sys.stdout, "isatty", return_value=False):
                with patch.object(sys.stderr, "isatty", return_value=False):
                    with patch("norfront_claw.prompt_keys._read_secret") as read:
                        ensure_boot_keys(load_config(self.root), command="doctor")
                        read.assert_not_called()

    def test_no_prompt_before_or_after_subcommand(self) -> None:
        with patch("norfront_claw.prompt_keys._stdio_can_prompt", return_value=True):
            with patch("norfront_claw.prompt_keys._read_secret") as read:
                with patch("sys.stdout", new=StringIO()):
                    rc1 = main(
                        ["--no-prompt", "--repo", str(self.root), "doctor", "--json"]
                    )
                    rc2 = main(
                        ["--repo", str(self.root), "doctor", "--no-prompt", "--json"]
                    )
        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)
        read.assert_not_called()

    def test_already_set_env_does_not_prompt(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "already-set-from-env-aaaa"
        os.environ["TYPESAFE_API_KEY"] = "already-set-typesafe-bbbb"
        with patch("norfront_claw.prompt_keys._stdio_can_prompt", return_value=True):
            with patch("norfront_claw.prompt_keys._read_secret") as read:
                ensure_boot_keys(load_config(self.root), command="doctor")
                read.assert_not_called()
        self.assertFalse((self.root / "claw.env").exists())

    def test_tty_run_prompts_deepseek_not_typesafe(self) -> None:
        with patch("norfront_claw.prompt_keys._stdio_can_prompt", return_value=True):
            with patch("norfront_claw.prompt_keys._read_secret") as read:
                read.return_value = ""
                with patch("sys.stdout", new=StringIO()):
                    with patch("sys.stderr", new=StringIO()):
                        rc = main(
                            ["--repo", str(self.root), "run", "Reply with pong"]
                        )
        read.assert_called_once()
        self.assertIn("DEEPSEEK_API_KEY", read.call_args[0][0])
        self.assertNotIn("TYPESAFE", read.call_args[0][0])
        self.assertNotEqual(rc, 0)
        self.assertFalse((self.root / "claw.env").exists())

    def test_choose_tty_empty_keeps_missing_behavior(self) -> None:
        _drop_claw_jev_modules()
        _write_jev_stub(self.root)
        try:
            with patch("norfront_claw.prompt_keys._stdio_can_prompt", return_value=True):
                with patch("norfront_claw.prompt_keys._read_secret", return_value="") as read:
                    with patch("sys.stdout", new=StringIO()):
                        with patch("sys.stderr", new=StringIO()) as err:
                            rc = main(
                                [
                                    "--repo",
                                    str(self.root),
                                    "choose",
                                    "https://example.com",
                                    "stop",
                                ]
                            )
            read.assert_called()
            self.assertEqual(rc, 2)
            self.assertIn("TYPESAFE_API_KEY", err.getvalue())
            self.assertNotIn(SECRET, err.getvalue())
            self.assertFalse((self.root / "claw.env").exists())
        finally:
            _drop_claw_jev_modules()


if __name__ == "__main__":
    unittest.main()
