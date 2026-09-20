from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from norfront_claw.browser import (
    AdapterMissing,
    MissingBrowserAdapter,
    ObserveResult,
    PolicyUnavailable,
    load_browser_adapter,
)
from norfront_claw.config import load_config


class BrowserHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "BRIEF.md").write_text("brief\n", encoding="utf-8")
        (self.root / "product").mkdir()
        os.environ["CLAW_REPO"] = str(self.root)
        os.environ.pop("CLAW_BROWSER_ADAPTER", None)
        os.environ.pop("TYPESAFE_API_KEY", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_observe_result_forbids_typesafe(self) -> None:
        with self.assertRaises(ValueError):
            ObserveResult(
                ok=True,
                url="https://example.com",
                actions=(),
                adapter="bad",
                used_typesafe=True,
            )

    def test_missing_adapter_observe_and_guards_skip_typesafe(self) -> None:
        cfg = load_config(self.root)
        adapter = load_browser_adapter(cfg)
        self.assertIsInstance(adapter, MissingBrowserAdapter)
        obs = adapter.observe("https://example.com")
        self.assertFalse(obs.used_typesafe)
        self.assertFalse(obs.ok)
        guards = adapter.check_guards()
        self.assertFalse(guards.used_typesafe)
        self.assertTrue(guards.ok)
        with self.assertRaises(AdapterMissing):
            next(adapter.run_policy("https://example.com", "open the page"))

    def test_spec_loader_observe_without_typesafe(self) -> None:
        import sys

        moddir = self.root / "mod"
        moddir.mkdir()
        (moddir / "hook.py").write_text(
            Path(__file__).with_name("fake_adapter.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        sys.path.insert(0, str(moddir))
        os.environ["CLAW_BROWSER_ADAPTER"] = "hook:create_adapter"
        cfg = load_config(self.root)
        adapter = load_browser_adapter(cfg)
        self.assertEqual(adapter.name, "fake-jev")
        obs = adapter.observe("https://example.com")
        self.assertTrue(obs.ok)
        self.assertFalse(obs.used_typesafe)
        self.assertFalse(cfg.typesafe_key)
        g = adapter.check_guards()
        self.assertFalse(g.used_typesafe)
        with self.assertRaises(PolicyUnavailable):
            next(adapter.run_policy("https://example.com", "find the heading"))

    def test_file_adapter_discovery(self) -> None:
        jev = self.root / "product" / "jev"
        jev.mkdir()
        (jev / "adapter.py").write_text(
            Path(__file__).with_name("fake_adapter.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        cfg = load_config(self.root)
        adapter = load_browser_adapter(cfg)
        self.assertEqual(adapter.name, "fake-jev")
        obs = adapter.observe("https://example.com")
        self.assertTrue(obs.ok)
        self.assertFalse(obs.used_typesafe)


if __name__ == "__main__":
    unittest.main()
