"""Secret-free projection for the operator console snapshot."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

PRODUCT = Path(__file__).resolve().parent.parent
SCRIPT = PRODUCT / "ui" / "write_status.py"


def _load():
    spec = importlib.util.spec_from_file_location("claw_ui_write_status", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("write_status.py missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UiStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.mod = _load()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)

    def test_project_keeps_presence_and_drops_secret(self) -> None:
        secret = "ui-status-must-not-echo-this"
        os.environ["DEEPSEEK_API_KEY"] = secret
        snapshot = self.mod.project_snapshot(
            {
                "ok": True,
                "host": "linux",
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
                "adapter": "fake-jev",
                "keys": {
                    "DEEPSEEK_API_KEY": "set",
                    "TYPESAFE_API_KEY": "missing",
                },
                "checks": [
                    {
                        "id": "typesafe",
                        "ok": True,
                        "warning": True,
                        "detail": "observe and guards do not need it",
                    }
                ],
                "stubbed": ["desktop-watch-takeover"],
                "vm": {
                    "selected": "qemu",
                    "selected_source": "default",
                    "accel": "tcg",
                    "r2_vm_boundary": True,
                    "backends": [
                        {"id": "qemu", "live_start": "default", "present": True, "selected": True}
                    ],
                },
            }
        )
        blob = json.dumps(snapshot)
        self.assertNotIn(secret, blob)
        self.assertEqual(snapshot["keys"]["DEEPSEEK_API_KEY"], "set")
        self.assertEqual(snapshot["keys"]["TYPESAFE_API_KEY"], "missing")
        self.assertEqual(snapshot["keys"]["GH_TOKEN"], "missing")
        self.assertFalse(snapshot["browser"]["observe_needs_key"])
        self.assertTrue(snapshot["browser"]["choose_needs_key"])
        self.assertEqual(snapshot["source"], "local")

    def test_project_refuses_raw_key_material(self) -> None:
        with self.assertRaises(self.mod.StatusError):
            self.mod.project_snapshot(
                {"keys": {"DEEPSEEK_API_KEY": "not-a-presence-label"}}
            )

    def test_project_refuses_secret_copied_into_detail(self) -> None:
        secret = "ui-status-leak-sentinel"
        os.environ["TYPESAFE_API_KEY"] = secret
        with self.assertRaises(self.mod.StatusError) as ctx:
            self.mod.project_snapshot(
                {
                    "keys": {"TYPESAFE_API_KEY": "set"},
                    "checks": [{"id": "leak", "ok": False, "detail": f"saw {secret}"}],
                }
            )
        self.assertNotIn(secret, str(ctx.exception))

    def test_build_snapshot_on_bare_repo(self) -> None:
        secret = "bare-repo-doctor-must-not-print"
        os.environ["DEEPSEEK_API_KEY"] = secret
        os.environ.pop("TYPESAFE_API_KEY", None)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "BRIEF.md").write_text("brief\n", encoding="utf-8")
            (root / "product").mkdir()
            snapshot = self.mod.build_snapshot(root)
        blob = json.dumps(snapshot)
        self.assertNotIn(secret, blob)
        self.assertEqual(snapshot["keys"]["DEEPSEEK_API_KEY"], "set")
        self.assertEqual(snapshot["keys"]["TYPESAFE_API_KEY"], "missing")
        self.assertIn(snapshot["brains"][0]["id"], {"prime", "openhands", "openclaw", "goose"})
