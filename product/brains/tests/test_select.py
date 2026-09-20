from __future__ import annotations

import json
import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import _path  # noqa: F401
from claw_brains.cli import main
from claw_brains.config import load_config
from claw_brains.registry import select, selected_id, selected_source


class SelectTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "BRIEF.md").write_text("brief\n", encoding="utf-8")
        (self.root / "product").mkdir()
        os.environ.clear()
        os.environ.update(
            {
                "PATH": self._old.get("PATH", "/usr/bin"),
                "HOME": self._old.get("HOME", str(self.root)),
                "CLAW_REPO": str(self.root),
                "CLAW_BRAINS_HOME": str(self.root / "brains-home"),
                "CLAW_WORKSPACE": str(self.root / "work"),
            }
        )
        os.environ.pop("CLAW_BRAIN", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_default_is_prime(self) -> None:
        cfg = load_config(self.root)
        self.assertEqual(selected_id(cfg), "prime")
        self.assertEqual(selected_source(cfg)[1], "default")

    def test_select_persists_goose(self) -> None:
        cfg = load_config(self.root)
        self.assertEqual(select("goose", cfg), "goose")
        cfg = load_config(self.root)
        self.assertEqual(selected_id(cfg), "goose")
        self.assertEqual(selected_source(cfg)[1], "file")
        path = self.root / "brains-home" / "selected"
        self.assertEqual(path.read_text(encoding="utf-8").strip(), "goose")

    def test_env_wins_over_file(self) -> None:
        select("goose", load_config(self.root))
        os.environ["CLAW_BRAIN"] = "openhands"
        cfg = load_config(self.root)
        self.assertEqual(selected_id(cfg), "openhands")
        self.assertEqual(selected_source(cfg)[1], "env")

    def test_cli_select_json(self) -> None:
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["select", "openclaw", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["selected"], "openclaw")
        with patch("sys.stdout", new=StringIO()) as out:
            rc = main(["selected", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["id"], "openclaw")
        self.assertEqual(payload["source"], "file")

    def test_alias_open_hands(self) -> None:
        self.assertEqual(select("open-hands", load_config(self.root)), "openhands")


if __name__ == "__main__":
    unittest.main()
