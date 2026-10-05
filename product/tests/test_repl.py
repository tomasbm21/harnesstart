from __future__ import annotations

import io
import unittest
from pathlib import Path

from norfront_claw import boot
from norfront_claw.repl import run_repl


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str]) -> int:
        self.calls.append(list(argv))
        return 0


class ReplTest(unittest.TestCase):
    def _run(self, script: str, **kwargs):
        out = io.StringIO()
        code = run_repl(
            Path("."),
            stdin=io.StringIO(script),
            stdout=out,
            **kwargs,
        )
        return code, out.getvalue()

    def test_bare_text_runs_the_crew(self) -> None:
        run = _Recorder()
        code, out = self._run("Add a phone-width form\nquit\n", run_command=run)
        self.assertEqual(code, 0)
        self.assertEqual(run.calls, [["crew", "Add a phone-width form"]])
        self.assertIn("This window now takes typing", out)

    def test_known_subcommand_is_passed_through(self) -> None:
        run = _Recorder()
        _, _ = self._run("status\nquit\n", run_command=run)
        self.assertEqual(run.calls, [["status"]])

    def test_crew_and_run_need_an_argument(self) -> None:
        run = _Recorder()
        _, out = self._run("crew\nrun\nquit\n", run_command=run)
        self.assertEqual(run.calls, [])
        self.assertIn("Give the crew a task", out)
        self.assertIn("run <task>", out)

    def test_quit_calls_stop_once(self) -> None:
        stopped: list[str] = []
        run = _Recorder()
        code, _ = self._run(
            "quit\n",
            run_command=run,
            stop=lambda: stopped.append("stop"),
        )
        self.assertEqual(code, 0)
        self.assertEqual(stopped, ["stop"])

    def test_eof_also_stops(self) -> None:
        stopped: list[str] = []
        # No quit line: piped input just ends.
        code, _ = self._run("", run_command=_Recorder(), stop=lambda: stopped.append("s"))
        self.assertEqual(code, 0)
        self.assertEqual(stopped, ["s"])

    def test_help_and_ui_and_clear(self) -> None:
        opened: list[str] = []
        _, out = self._run(
            "help\nui\nclear\nquit\n",
            run_command=_Recorder(),
            reopen=lambda: opened.append("ui"),
        )
        self.assertEqual(opened, ["ui"])
        self.assertIn("coding crew", out)
        self.assertIn("Opened the console.", out)

    def test_blank_lines_are_ignored(self) -> None:
        run = _Recorder()
        _, _ = self._run("\n\n   \nquit\n", run_command=run)
        self.assertEqual(run.calls, [])


class BootWiringTest(unittest.TestCase):
    def setUp(self) -> None:
        import os
        import tempfile

        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XDG_DATA_HOME"] = self.tmp.name

    def tearDown(self) -> None:
        import os

        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def _hooks(self, **overrides):
        defaults = {
            "port_open": lambda: False,
            "ensure_node": lambda: "/usr/bin/node",
            "install_console": lambda: None,
            "ensure_prime": lambda: "",
            "ensure_jev": lambda: "",
            "refresh": lambda *_a: None,
            "start_console": lambda: None,
            "open_browser": lambda: None,
            "wait": lambda _proc: 41,
            "ready": lambda: True,
            "interactive": None,
        }
        defaults.update(overrides)
        return boot.BootHooks(**defaults)

    def test_interactive_used_on_a_tty(self) -> None:
        seen: list[int] = []
        old = boot.stdin_is_tty
        boot.stdin_is_tty = lambda: True
        try:
            code = boot.run_boot(
                self._hooks(interactive=lambda proc: seen.append(proc) or 0)
            )
        finally:
            boot.stdin_is_tty = old
        self.assertEqual(code, 0)
        self.assertEqual(len(seen), 1)

    def test_falls_back_to_wait_without_a_tty(self) -> None:
        old = boot.stdin_is_tty
        boot.stdin_is_tty = lambda: False
        try:
            code = boot.run_boot(
                self._hooks(interactive=lambda proc: 99, wait=lambda _proc: 7)
            )
        finally:
            boot.stdin_is_tty = old
        self.assertEqual(code, 7)


if __name__ == "__main__":
    unittest.main()
