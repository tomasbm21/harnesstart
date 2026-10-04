#!/usr/bin/env python3
"""Build NorfrontClaw-windows-x64.zip.

The zip is a release asset. Do not commit it, and do not commit the
Windows node_modules it contains. Console native modules are installed
for win32-x64, not for the Linux machine that runs this script.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CACHE = HERE / ".cache"
DIST = HERE / "dist"
ZIP_NAME = "NorfrontClaw-windows-x64.zip"

SKIP_DIR_NAMES = frozenset(
    {
        "node_modules",
        "__pycache__",
        ".venv",
        "dist",
        "dist-ssr",
        ".git",
        ".pytest_cache",
        ".cache",
        ".worktrees",
    }
)
SKIP_FILE_NAMES = frozenset({"claw.env", ".env", "status.local.json"})
SKIP_SUFFIXES = frozenset({".pyc", ".pem", ".key"})

_FOREIGN_PLATFORM = re.compile(
    r"(^|-)(linux|darwin|android|freebsd|openharmony|sunos|aix)(-|$)|"
    r"win32-arm64|win32-ia32|arm-eabi",
    re.IGNORECASE,
)
_WIN32_X64 = re.compile(r"win32-x64|windows-64", re.IGNORECASE)

ZIP_README = """Norfront Claw

Double-click start.exe.

A window stays open while the app is running. Close that window to stop.
The page opens at http://127.0.0.1:5173

The first time, the window can ask for a DeepSeek key. Typing is hidden.
It can also download the brain program. Chrome is not inside this zip.
If hardware KVM or a TypeSafe key is missing, the page says so in a sentence.

Opening start.exe again while that window is still open does not start a
second copy. It opens the page again.
"""


def repo_path_excluded(relative: Path) -> bool:
    if any(part in SKIP_DIR_NAMES for part in relative.parts):
        return True
    if relative.name in SKIP_FILE_NAMES:
        return True
    return relative.suffix.lower() in SKIP_SUFFIXES


def python_pth_with_product(existing: str) -> str:
    """Embeddable Python ignores PYTHONPATH, so list the product trees here."""
    extras = (r"..\..\product", r"..\..\product\vm")
    lines = existing.splitlines()
    body = "\n".join(lines).rstrip("\n")
    for extra in extras:
        if not any(line.strip() == extra for line in lines):
            body = f"{body}\n{extra}" if body else extra
            lines = body.splitlines()
    if not body.endswith("\n"):
        body += "\n"
    return body


def windows_cmd_for_target(bin_dir: Path, entry: Path) -> str | None:
    if not entry.is_symlink():
        return None
    target = entry.resolve()
    if not target.is_file():
        return None
    rel = os.path.relpath(target, bin_dir).replace("/", "\\")
    return f'@echo off\r\nnode "%~dp0{rel}" %*\r\n'


def is_foreign_platform_dir(name: str) -> bool:
    if _WIN32_X64.search(name) and not re.search(
        r"linux|darwin|android|freebsd|openharmony", name, re.IGNORECASE
    ):
        return False
    return _FOREIGN_PLATFORM.search(name) is not None


def is_elf(header: bytes) -> bool:
    return header.startswith(b"\x7fELF")


def is_pe(header: bytes) -> bool:
    return header.startswith(b"MZ")


def _secretish(name: str) -> bool:
    upper = name.upper()
    return any(
        part in upper
        for part in ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL")
    )


def scrubbed_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not _secretish(key)}


def _url_ok(url: str) -> bool:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return 200 <= getattr(response, "status", 200) < 300
    except Exception:
        return False


def python_embed_url() -> tuple[str, str]:
    for minor in range(20, 6, -1):
        version = f"3.12.{minor}"
        url = (
            "https://www.python.org/ftp/python/"
            f"{version}/python-{version}-embed-amd64.zip"
        )
        if _url_ok(url):
            return version, url
    raise SystemExit("could not find a Python 3.12 Windows embeddable zip")


def node_archive() -> tuple[str, str]:
    sys.path.insert(0, str(REPO / "product"))
    from norfront_claw.boot import NODE_VERSION

    name = f"node-{NODE_VERSION}-win-x64.zip"
    return NODE_VERSION, f"https://nodejs.org/dist/{NODE_VERSION}/{name}"


def download(url: str, dest: Path) -> None:
    if dest.is_file() and dest.stat().st_size > 1_000_000:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"downloading {dest.name}")
    urllib.request.urlretrieve(url, tmp)
    if tmp.stat().st_size < 1_000_000:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"download looked empty: {dest.name}")
    tmp.replace(dest)


def compile_exe(src: Path, dest: Path) -> None:
    gcc = shutil.which("x86_64-w64-mingw32-gcc")
    if not gcc:
        raise SystemExit("x86_64-w64-mingw32-gcc is required to build start.exe")
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [gcc, "-O2", "-s", "-municode", "-mconsole", "-o", str(dest), str(src)],
        check=True,
    )


def _safe_member(name: str) -> bool:
    path = Path(name)
    return not path.is_absolute() and ".." not in path.parts


def extract_zip_root(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as packed:
        for info in packed.infolist():
            if info.is_dir() or not _safe_member(info.filename):
                continue
            target = dest / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with packed.open(info) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)


def extract_node(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as packed:
        names = [info.filename for info in packed.infolist() if info.filename]
        top = names[0].split("/")[0]
        prefix = top + "/"
        for info in packed.infolist():
            if not info.filename.startswith(prefix) or info.is_dir():
                continue
            inner = info.filename[len(prefix) :]
            if not inner or not _safe_member(inner):
                continue
            target = dest / inner
            target.parent.mkdir(parents=True, exist_ok=True)
            with packed.open(info) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)


def copy_product(dest: Path) -> None:
    src = REPO / "product"
    for path in src.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(src)
        if repo_path_excluded(rel):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def install_console(ui: Path) -> None:
    if not str(ui.resolve()).startswith(str(DIST.resolve())):
        raise SystemExit("refusing to npm-install outside the package stage")
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm is required on the build machine")
    env = scrubbed_env()
    env["npm_config_cache"] = str(CACHE / "npm")
    env["npm_config_fund"] = "false"
    env["npm_config_audit"] = "false"
    subprocess.run(
        [npm, "ci", "--ignore-scripts", "--cpu=x64", "--os=win32"],
        cwd=ui,
        env=env,
        check=True,
        timeout=600,
    )


def write_windows_bins(ui: Path) -> int:
    bindir = ui / "node_modules" / ".bin"
    if not bindir.is_dir():
        return 0
    written = 0
    for entry in bindir.iterdir():
        text = windows_cmd_for_target(bindir, entry)
        if text is None:
            continue
        cmd = bindir / f"{entry.name}.cmd"
        cmd.write_bytes(text.encode("ascii"))
        written += 1
    return written


def remove_foreign_platform_dirs(node_modules: Path) -> list[str]:
    found: list[Path] = []
    for path in node_modules.rglob("*"):
        if path.is_dir() and is_foreign_platform_dir(path.name):
            found.append(path)
    found.sort(key=lambda item: len(item.parts), reverse=True)
    removed: list[str] = []
    for path in found:
        if path.exists():
            shutil.rmtree(path)
            removed.append(path.name)
    return removed


def assert_win32_natives(node_modules: Path) -> None:
    pe = 0
    elf: list[str] = []
    win_dirs = 0
    foreign: list[str] = []
    for path in node_modules.rglob("*"):
        if path.is_dir() and is_foreign_platform_dir(path.name):
            foreign.append(path.name)
        if path.is_dir() and _WIN32_X64.search(path.name):
            win_dirs += 1
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".node", ".dll", ".exe"}:
            continue
        header = path.read_bytes()[:4]
        if is_elf(header):
            elf.append(str(path.relative_to(node_modules)))
        elif is_pe(header):
            pe += 1
    if foreign:
        raise SystemExit("linux or other non-win32 packages still installed: " + ", ".join(foreign[:8]))
    if elf:
        raise SystemExit("refusing to ship Linux native modules: " + ", ".join(elf[:8]))
    if win_dirs < 1 or pe < 1:
        raise SystemExit("Windows console native modules were not installed")


def assert_no_secrets(stage: Path) -> None:
    for path in stage.rglob("*"):
        if not path.is_file():
            continue
        if path.name in SKIP_FILE_NAMES or path.suffix.lower() in {".pem", ".key"}:
            raise SystemExit(f"refusing to pack {path.name}")


def write_zip(stage: Path, dest: Path) -> None:
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as packed:
        for path in sorted(stage.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(stage).as_posix()
            packed.write(path, rel)


def build() -> Path:
    sys.path.insert(0, str(REPO / "product"))
    CACHE.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    stage = DIST / "stage"
    if stage.exists():
        shutil.rmtree(stage)

    py_version, py_url = python_embed_url()
    node_version, node_url = node_archive()
    py_zip = CACHE / f"python-{py_version}-embed-amd64.zip"
    node_zip = CACHE / f"node-{node_version}-win-x64.zip"
    download(py_url, py_zip)
    download(node_url, node_zip)

    start_exe = CACHE / "start.exe"
    npm_exe = CACHE / "npm.exe"
    compile_exe(HERE / "start.c", start_exe)
    compile_exe(HERE / "npm_shim.c", npm_exe)

    runtime_py = stage / "runtime" / "python"
    runtime_node = stage / "runtime" / "node"
    extract_zip_root(py_zip, runtime_py)
    extract_node(node_zip, runtime_node)
    shutil.copy2(npm_exe, runtime_node / "npm.exe")
    shutil.copy2(start_exe, stage / "start.exe")

    pth_files = list(runtime_py.glob("python*._pth"))
    if len(pth_files) != 1:
        raise SystemExit("portable Python did not contain one ._pth file")
    pth = pth_files[0]
    pth.write_text(python_pth_with_product(pth.read_text(encoding="utf-8")), encoding="utf-8")

    copy_product(stage / "product")
    for name in ("BRIEF.md", "claw.env.example"):
        src = REPO / name
        if src.is_file():
            shutil.copy2(src, stage / name)
    (stage / "README.txt").write_text(ZIP_README, encoding="utf-8")

    ui = stage / "product" / "ui"
    install_console(ui)
    write_windows_bins(ui)
    remove_foreign_platform_dirs(ui / "node_modules")
    assert_win32_natives(ui / "node_modules")
    assert_no_secrets(stage)

    if not (stage / "start.exe").is_file():
        raise SystemExit("start.exe missing from the zip root")
    if not (runtime_py / "python.exe").is_file():
        raise SystemExit("portable python.exe missing")
    if not (runtime_node / "node.exe").is_file():
        raise SystemExit("portable node.exe missing")

    dest = DIST / ZIP_NAME
    write_zip(stage, dest)
    print(f"wrote {dest} ({dest.stat().st_size} bytes)")
    return dest


def main() -> int:
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
