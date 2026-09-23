from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PRODUCT = Path(__file__).resolve().parent.parent
REPO = PRODUCT.parent
CLAW = PRODUCT / "claw"


class CliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        # Isolate secrets so doctor output can be scanned.
        for key in (
            "DEEPSEEK_API_KEY",
            "TYPESAFE_API_KEY",
            "TEXT_MODEL_API_KEY",
            "WEB_API_KEY",
            "GH_TOKEN",
            "CLAW_BROWSER_ADAPTER",
        ):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def _run(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged = os.environ.copy()
        if env:
            merged.update(env)
        merged["PYTHONPATH"] = str(PRODUCT) + os.pathsep + merged.get("PYTHONPATH", "")
        return subprocess.run(
            [sys.executable, "-m", "norfront_claw", *args],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(REPO),
            env=merged,
        )

    def test_version(self) -> None:
        proc = self._run("--version")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("0.0.1", proc.stdout)

    def _bare_repo(self) -> Path:
        root = Path(tempfile.mkdtemp(prefix="harness-", dir=self.tmp.name))
        (root / "BRIEF.md").write_text("brief\n", encoding="utf-8")
        (root / "product").mkdir()
        return root

    def test_doctor_json_on_linux_without_keys(self) -> None:
        secret = "do-not-print-this-secret-key-xyz"
        repo = self._bare_repo()
        proc = self._run(
            "--repo",
            str(repo),
            "doctor",
            "--json",
            env={"DEEPSEEK_API_KEY": secret, "TYPESAFE_API_KEY": ""},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn(secret, proc.stdout)
        self.assertNotIn(secret, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["host"], "linux")
        self.assertFalse(payload["r2_isolated"])
        self.assertEqual(payload["keys"]["DEEPSEEK_API_KEY"], "set")
        self.assertEqual(payload["keys"]["TYPESAFE_API_KEY"], "missing")
        self.assertIn("r2-vm-computer", payload["stubbed"])
        ids = {c["id"]: c for c in payload["checks"]}
        self.assertTrue(ids["linux"]["ok"])
        self.assertIn("not need it", ids["typesafe"]["detail"])

    def test_guards_without_typesafe(self) -> None:
        proc = self._run("--repo", str(self._bare_repo()), "guards", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["used_typesafe"])
        self.assertTrue(payload["ok"])

    def test_observe_missing_adapter_does_not_demand_typesafe(self) -> None:
        proc = self._run(
            "--repo",
            str(self._bare_repo()),
            "observe",
            "https://example.com",
            "--json",
        )
        combined = proc.stdout + proc.stderr
        self.assertNotIn("TYPESAFE_API_KEY", combined)
        self.assertNotIn("paste", combined.lower())
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["used_typesafe"])

    def test_browse_without_adapter_does_not_ask_for_typesafe(self) -> None:
        proc = self._run(
            "--repo",
            str(self._bare_repo()),
            "browse",
            "https://example.com",
            "open the heading",
        )
        self.assertEqual(proc.returncode, 1)
        combined = proc.stderr + proc.stdout
        self.assertIn("product/jev", combined)
        self.assertNotIn("paste the key", combined.lower())
        self.assertNotIn("sk-", combined)

    def test_stub_claw_jev_choose_without_key_exits_2(self) -> None:
        from test_claw_jev_hook import _write_stub

        repo = self._bare_repo()
        _write_stub(repo)
        proc = self._run(
            "--repo",
            str(repo),
            "choose",
            "https://example.com",
            "stop at the heading",
        )
        self.assertEqual(proc.returncode, 2, proc.stderr + proc.stdout)
        self.assertIn("TYPESAFE_API_KEY", proc.stderr)
        self.assertIn("chat", proc.stderr.lower())

    def test_stub_claw_jev_policy_and_observe(self) -> None:
        from test_claw_jev_hook import _write_stub

        repo = self._bare_repo()
        _write_stub(repo)
        pol = self._run("--repo", str(repo), "policy")
        self.assertEqual(pol.returncode, 0, pol.stderr)
        status = json.loads(pol.stdout)
        self.assertFalse(status["choose"])
        self.assertFalse(status["observe_needs_key"])
        obs = self._run("--repo", str(repo), "observe", "https://example.com", "--json")
        self.assertEqual(obs.returncode, 0, obs.stderr + obs.stdout)
        payload = json.loads(obs.stdout)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["used_typesafe"])
        self.assertEqual(payload["adapter"], "claw-jev")

    def test_run_blocks_irreversible(self) -> None:
        proc = self._run(
            "--repo",
            str(self._bare_repo()),
            "run",
            "checkout and pay with the saved card",
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("blocked pay", proc.stderr)

    def test_script_entrypoint_exists(self) -> None:
        self.assertTrue(CLAW.is_file())
        self.assertTrue(os.access(CLAW, os.X_OK), "product/claw must be executable")

    def test_no_args_is_five_line_you_are_here(self) -> None:
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertEqual(len(lines), 5, proc.stdout)
        self.assertTrue(lines[0].startswith("Open the console:"))
        self.assertIn("./launch", lines[0])
        self.assertIn("./product/claw ui", lines[0])
        lowered = proc.stdout.lower()
        self.assertNotIn("hermes", lowered)
        self.assertNotIn("claw-brains", lowered)

    def test_you_are_here_windows_points_at_bat(self) -> None:
        from norfront_claw.cli import you_are_here_text

        lines = you_are_here_text(windows=True).splitlines()
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[0], "Open the console: double-click Launch Claw.bat")

    def test_help_still_lists_subcommands(self) -> None:
        proc = self._run("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("doctor", proc.stdout)
        self.assertIn("ui", proc.stdout)
        self.assertIn("test", proc.stdout)

    def test_launch_files_boot_the_whole_app(self) -> None:
        bat = (REPO / "Launch Claw.bat").read_text(encoding="utf-8")
        launch = (REPO / "launch").read_text(encoding="utf-8")
        self.assertTrue(os.access(REPO / "launch", os.X_OK))
        for text in (bat, launch):
            self.assertIn("norfront_claw.boot", text)
            self.assertNotIn("claw-brains", text)
            self.assertNotIn("npm run dev", text)
            self.assertNotIn("Install Node from https://nodejs.org", text)
        self.assertIn("winget install", bat)
        self.assertIn("uv python install", launch)

    def test_ui_execs_launch_and_does_not_prompt(self) -> None:
        from unittest.mock import patch

        from norfront_claw.cli import main

        with patch("norfront_claw.prompt_keys._read_secret", side_effect=AssertionError("prompted")):
            with patch("norfront_claw.cli.os.execv", side_effect=SystemExit(7)) as execv:
                with self.assertRaises(SystemExit) as ctx:
                    main(["ui"])
        self.assertEqual(ctx.exception.code, 7)
        script = execv.call_args.args[0]
        self.assertTrue(str(script).endswith("/launch"), script)

    def test_wrapper_no_args_does_not_prompt(self) -> None:
        env = os.environ.copy()
        env["CLAW_NO_KEY_PROMPT"] = "1"
        proc = subprocess.run(
            [str(CLAW)],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(REPO),
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(proc.stdout.splitlines()), 5)


if __name__ == "__main__":
    unittest.main()
