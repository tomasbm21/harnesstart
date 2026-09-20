from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from norfront_claw.config import load_config, parse_env_file, presence_label
from norfront_claw.secrets import redact


class EnvTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = os.environ.copy()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "BRIEF.md").write_text("brief\n", encoding="utf-8")
        (self.root / "product").mkdir()
        os.environ["CLAW_REPO"] = str(self.root)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old)
        self.tmp.cleanup()

    def test_parse_env_strips_comments_and_quotes(self) -> None:
        path = self.root / "claw.env"
        path.write_text(
            'DEEPSEEK_API_KEY="abc123"  # comment\n'
            "CLAW_MODEL=deepseek-v4-pro\n"
            "# ignored\n",
            encoding="utf-8",
        )
        parsed = parse_env_file(path)
        self.assertEqual(parsed["DEEPSEEK_API_KEY"], "abc123")
        self.assertEqual(parsed["CLAW_MODEL"], "deepseek-v4-pro")

    def test_process_env_wins_over_file(self) -> None:
        (self.root / "claw.env").write_text("CLAW_MODEL=from-file\n", encoding="utf-8")
        os.environ["CLAW_MODEL"] = "from-process"
        cfg = load_config(self.root)
        self.assertEqual(cfg.model, "from-process")

    def test_stored_in_hermes_is_not_present(self) -> None:
        (self.root / "claw.env").write_text(
            "DEEPSEEK_API_KEY=__stored_in_hermes__\n", encoding="utf-8"
        )
        os.environ.pop("DEEPSEEK_API_KEY", None)
        cfg = load_config(self.root)
        self.assertFalse(cfg.deepseek_key)

    def test_repr_and_redact_never_show_key(self) -> None:
        os.environ["DEEPSEEK_API_KEY"] = "super-secret-test-key-9999"
        cfg = load_config(self.root)
        dumped = repr(cfg)
        self.assertNotIn("super-secret-test-key-9999", dumped)
        self.assertEqual(presence_label(cfg.deepseek_key), "set")
        self.assertEqual(redact("token=super-secret-test-key-9999"), "token=***")


if __name__ == "__main__":
    unittest.main()
