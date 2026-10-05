from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from norfront_claw.boot import (
    BOOT_STEP_TIMEOUT,
    BootHooks,
    ensure_jev,
    ensure_prime,
    node_archive,
    plain_notes,
    run_boot,
)


def _hooks(**overrides: object) -> BootHooks:
    defaults = {
        "port_open": lambda: False,
        "ensure_node": lambda: "/usr/bin/node",
        "install_console": lambda: None,
        "ensure_prime": lambda: "",
        "ensure_jev": lambda: "",
        "refresh": lambda *_args: None,
        "start_console": lambda: None,
        "open_browser": lambda: None,
        "wait": lambda _proc: 0,
        "ready": lambda: True,
    }
    defaults.update(overrides)
    return BootHooks(**defaults)


class BootTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XDG_DATA_HOME"] = self.tmp.name

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_notes_are_sentences(self) -> None:
        notes = plain_notes(
            {"vm": {"r2_hardware_kvm": False}, "keys": {"TYPESAFE_API_KEY": "missing"}},
            ["npm install the console", "The brain program is not installed. The console, checks, and crew still run."],
        )
        blob = "\n".join(notes)
        self.assertIn("Hardware KVM", blob)
        self.assertIn("TypeSafe", blob)
        self.assertIn("crew is in this window", blob)
        self.assertIn("brain program", blob)
        self.assertNotIn("npm", blob)
        self.assertNotIn("./", blob)
        self.assertNotIn("claw-brains", blob)

    def test_second_launch_does_not_install_or_start(self) -> None:
        seen: list[str] = []
        code = run_boot(
            _hooks(
                port_open=lambda: True,
                ensure_node=lambda: seen.append("node"),
                install_console=lambda: seen.append("npm"),
                ensure_prime=lambda: seen.append("prime"),
                start_console=lambda: seen.append("vite"),
                refresh=lambda *_a: seen.append("refresh"),
                open_browser=lambda: seen.append("browser"),
            )
        )
        self.assertEqual(code, 0)
        self.assertEqual(seen, ["refresh", "browser"])

    def test_missing_node_keeps_the_checks(self) -> None:
        seen: dict[str, list[str]] = {}

        def refresh(no_prompt: bool, extra: list[str] | None = None) -> None:
            seen["prompt"] = [str(no_prompt)]
            seen["extra"] = list(extra or [])

        code = run_boot(
            _hooks(
                ensure_node=lambda: None,
                install_console=lambda: (_ for _ in ()).throw(AssertionError("npm")),
                ensure_jev=lambda: "The browser package is not installed. Looking at a page from the console still works.",
                refresh=refresh,
                start_console=lambda: (_ for _ in ()).throw(AssertionError("vite")),
            )
        )
        self.assertEqual(code, 0)
        self.assertEqual(seen["prompt"], ["False"])
        blob = " ".join(seen["extra"])
        self.assertIn("Node did not install", blob)
        self.assertIn("browser package", blob)

    def test_starts_console_once(self) -> None:
        order: list[str] = []

        class Proc:
            def terminate(self) -> None:
                order.append("term")

        code = run_boot(
            _hooks(
                install_console=lambda: order.append("npm"),
                refresh=lambda *_a: order.append("refresh"),
                start_console=lambda: order.append("vite") or Proc(),
                open_browser=lambda: order.append("browser"),
            )
        )
        self.assertEqual(code, 0)
        self.assertEqual(order, ["npm", "refresh", "vite", "browser"])

    def test_live_lock_is_left_alone(self) -> None:
        state = Path(self.tmp.name) / "norfront-claw" / "boot"
        state.mkdir(parents=True)
        (state / "boot.lock").write_text(str(os.getpid()), encoding="utf-8")
        seen: list[str] = []
        code = run_boot(
            _hooks(
                ensure_node=lambda: seen.append("node"),
                open_browser=lambda: seen.append("browser"),
            )
        )
        self.assertEqual(code, 0)
        self.assertEqual(seen, ["browser"])
        self.assertTrue((state / "boot.lock").is_file())

    def test_node_archive_names(self) -> None:
        linux = node_archive("linux", "x86_64")
        self.assertIsNotNone(linux)
        assert linux is not None
        self.assertIn("linux-x64", linux[0])
        self.assertTrue(linux[1].startswith("https://nodejs.org/dist/"))
        self.assertIsNone(node_archive("darwin", "x86_64"))

    def test_missing_jev_checkout_is_a_sentence(self) -> None:
        note = ensure_jev(Path(self.tmp.name))
        self.assertIn("not on this checkout", note)
        self.assertNotIn("pip", note)

    def test_progress_lines_are_flushed_before_slow_steps(self) -> None:
        buf = StringIO()
        with patch("sys.stdout", buf):
            code = run_boot(_hooks())
        self.assertEqual(code, 0)
        text = buf.getvalue()
        checking = text.index("Checking this machine.")
        brain = text.index("Downloading the brain program.")
        browser = text.index("Installing the browser package.")
        opening = text.index("Opening the page.")
        self.assertLess(checking, brain)
        self.assertLess(brain, browser)
        self.assertLess(browser, opening)
        self.assertNotIn("npm ", text)
        self.assertNotIn("claw.env", text)

    def test_brain_timeout_still_opens_the_page(self) -> None:
        buf = StringIO()
        with patch("sys.stdout", buf):
            code = run_boot(
                _hooks(
                    ensure_prime=lambda: (
                        "The brain program is not installed. "
                        "The console, checks, and crew still run."
                    )
                )
            )
        self.assertEqual(code, 0)
        text = buf.getvalue()
        self.assertIn("brain program is not installed", text)
        self.assertLess(text.index("brain program is not installed"), text.index("Opening the page."))

    def test_prime_download_uses_a_short_timeout(self) -> None:
        with patch("norfront_claw.boot.PrimeBrain") as brain:
            brain.return_value.which.return_value = None
            with patch("norfront_claw.boot.install_prime_agent") as install:
                install.side_effect = subprocess.TimeoutExpired("prime-agent", BOOT_STEP_TIMEOUT)
                note = ensure_prime(object())
        self.assertEqual(install.call_args.kwargs["timeout"], BOOT_STEP_TIMEOUT)
        self.assertLessEqual(BOOT_STEP_TIMEOUT, 20)
        self.assertIn("brain program is not installed", note)
        self.assertNotIn("http", note)
        self.assertNotIn("curl", note)
