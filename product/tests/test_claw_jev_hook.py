"""Import-path tests for `from claw_jev import ClawJev, observe, ...` (no Chrome)."""

from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from norfront_claw.browser import (
    ClawJevAdapter,
    PolicyUnavailable,
    load_browser_adapter,
)
from norfront_claw.config import load_config

STUB = textwrap.dedent(
    '''
    """Minimal claw_jev surface matching product/jev (no Chrome, no TypeSafe on observe/guards)."""
    import os

    class PolicyUnavailable(RuntimeError):
        pass

    class ClawJev:
        def observe(self, url, *, screenshot=False):
            return {
                "url": url,
                "title": "Example Domain",
                "actions": [
                    {"id": 1, "kind": "click", "label": "Learn more"},
                    {"id": 2, "kind": "wait", "label": "wait"},
                ],
            }

        def choose(self, page, goal, history=None):
            return choose(page, goal, history)

        def run(self, url, goal, **kwargs):
            require_choose()
            yield {"url": url, "goal": goal, "status": "stub-live", "elapsed_ms": 0, "history": []}

        def close(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def _present(name):
        return bool(os.environ.get(name, "").strip())

    def require_choose():
        if _present("TYPESAFE_API_KEY"):
            return
        raise PolicyUnavailable(
            "Live Jev choose()/run() need TYPESAFE_API_KEY in the environment "
            "(not chat). Observe and guards do not."
        )

    def observe(url, *, screenshot=False):
        with ClawJev() as session:
            return session.observe(url, screenshot=screenshot)

    def check_guards():
        return {
            "ok": True,
            "passed": 21,
            "checks": ["stub"] * 21,
            "model_calls": 0,
            "typesafe_required": False,
        }

    def choose(page, goal, history=None):
        require_choose()
        return {"operation": "WAIT", "goal": goal}

    def run(url, goal, **kwargs):
        require_choose()
        with ClawJev() as session:
            return list(session.run(url, goal, **kwargs))

    def policy_status():
        return {
            "choose": _present("TYPESAFE_API_KEY"),
            "type_text": _present("TEXT_MODEL_API_KEY"),
            "observe_needs_key": False,
            "guards_need_key": False,
        }

    def doctor():
        return {
            "chrome_binary": "/opt/google/chrome/chrome",
            "user_data_dir_ok": True,
            "cdp_ok": False,
            "policy": policy_status(),
        }
    '''
)


def _write_stub(root: Path) -> None:
    pkg = root / "product" / "jev" / "claw_jev"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(STUB, encoding="utf-8")


class ClawJevHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "BRIEF.md").write_text("brief\n", encoding="utf-8")
        (self.root / "product").mkdir()
        _write_stub(self.root)
        os.environ["CLAW_REPO"] = str(self.root)
        os.environ.pop("CLAW_BROWSER_ADAPTER", None)
        os.environ.pop("TYPESAFE_API_KEY", None)
        os.environ.pop("TEXT_MODEL_API_KEY", None)

    def tearDown(self) -> None:
        from norfront_claw.browser import _drop_claw_jev_modules

        _drop_claw_jev_modules()
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_imports_public_surface(self) -> None:
        cfg = load_config(self.root)
        adapter = load_browser_adapter(cfg)
        self.assertIsInstance(adapter, ClawJevAdapter)
        self.assertEqual(adapter.name, "claw-jev")
        info = adapter.doctor()
        self.assertTrue(info["present"])
        self.assertFalse(info["typesafe_required_for_observe"])
        self.assertFalse(info["typesafe_required_for_guards"])
        self.assertTrue(info["typesafe_required_for_choose"])
        status = adapter.policy_status()
        self.assertFalse(status["choose"])
        self.assertFalse(status["observe_needs_key"])
        self.assertNotIn("TYPESAFE_API_KEY", str(status))

    def test_observe_and_guards_without_typesafe(self) -> None:
        cfg = load_config(self.root)
        adapter = load_browser_adapter(cfg)
        obs = adapter.observe("https://example.com")
        self.assertTrue(obs.ok)
        self.assertFalse(obs.used_typesafe)
        self.assertGreaterEqual(len(obs.actions), 1)
        guards = adapter.check_guards()
        self.assertTrue(guards.ok)
        self.assertFalse(guards.used_typesafe)
        self.assertEqual(guards.passed, 21)

    def test_choose_and_run_need_env_key(self) -> None:
        cfg = load_config(self.root)
        adapter = load_browser_adapter(cfg)
        page = {"url": "https://example.com", "actions": []}
        with self.assertRaises(PolicyUnavailable) as ctx:
            adapter.choose(page, "open Learn more")
        self.assertIn("TYPESAFE_API_KEY", str(ctx.exception))
        self.assertIn("chat", str(ctx.exception).lower())
        with self.assertRaises(PolicyUnavailable):
            next(adapter.run_policy("https://example.com", "stop at the heading"))

    def test_choose_runs_when_key_is_in_env(self) -> None:
        os.environ["TYPESAFE_API_KEY"] = "not-a-real-key-do-not-print"
        cfg = load_config(self.root)
        adapter = load_browser_adapter(cfg)
        decision = adapter.choose({"url": "https://example.com"}, "wait")
        self.assertEqual(decision["operation"], "WAIT")
        self.assertNotIn("not-a-real-key-do-not-print", str(decision))
        self.assertNotIn("not-a-real-key-do-not-print", str(adapter.policy_status()))


if __name__ == "__main__":
    unittest.main()
