"""Packager rules: no secrets in the zip, Windows natives only."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[2] / "packaging" / "windows" / "build_windows_zip.py"
    spec = importlib.util.spec_from_file_location("build_windows_zip", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("packager missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WindowsPackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack = _load()

    def test_copy_skips_secrets_and_linux_modules(self) -> None:
        pack = self.pack
        self.assertTrue(pack.repo_path_excluded(Path("claw.env")))
        self.assertTrue(pack.repo_path_excluded(Path("ui") / "node_modules" / "vite"))
        self.assertTrue(pack.repo_path_excluded(Path("ui") / "public" / "status.local.json"))
        self.assertTrue(pack.repo_path_excluded(Path("norfront_claw") / "__pycache__" / "boot.pyc"))
        self.assertFalse(pack.repo_path_excluded(Path("norfront_claw") / "boot.py"))
        self.assertFalse(pack.repo_path_excluded(Path("ui") / "package.json"))

    def test_pth_points_at_product(self) -> None:
        text = self.pack.python_pth_with_product("python312.zip\n.\n\n# comment\n#import site\n")
        self.assertIn("python312.zip", text)
        self.assertIn("#import site", text)
        self.assertIn("..\\..\\product", text)
        self.assertIn("..\\..\\product\\vm", text)
        self.assertTrue(text.endswith("\n"))

    def test_foreign_platform_dirs(self) -> None:
        self.assertTrue(self.pack.is_foreign_platform_dir("binding-linux-x64-gnu"))
        self.assertTrue(self.pack.is_foreign_platform_dir("lightningcss-darwin-arm64"))
        self.assertFalse(self.pack.is_foreign_platform_dir("binding-win32-x64-msvc"))
        self.assertFalse(self.pack.is_foreign_platform_dir("vite"))

    def test_headers(self) -> None:
        self.assertTrue(self.pack.is_elf(b"\x7fELF\x02"))
        self.assertFalse(self.pack.is_pe(b"\x7fELF\x02"))
        self.assertTrue(self.pack.is_pe(b"MZ\x90\x00"))

    def test_start_exe_runs_python_unbuffered(self) -> None:
        text = (
            Path(__file__).resolve().parents[2] / "packaging" / "windows" / "start.c"
        ).read_text(encoding="utf-8")
        self.assertIn("PYTHONUNBUFFERED", text)
        self.assertIn("-u -m norfront_claw.boot", text)

    def test_scrub_drops_key_names(self) -> None:
        import os

        old = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = "should-not-pack"
        try:
            env = self.pack.scrubbed_env()
        finally:
            if old is None:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            else:
                os.environ["DEEPSEEK_API_KEY"] = old
        self.assertNotIn("DEEPSEEK_API_KEY", env)


if __name__ == "__main__":
    unittest.main()
