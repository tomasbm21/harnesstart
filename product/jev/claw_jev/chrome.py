"""Dedicated Chrome for Claw. Never the human profile. CDP on loopback."""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

DAEMON_NAME = "claw-jev"
DEFAULT_CDP_PORT = 9333

_DEFAULT_PROFILE_ROOTS = (
    Path.home() / ".config/google-chrome",
    Path.home() / ".config/google-chrome-beta",
    Path.home() / ".config/google-chrome-unstable",
    Path.home() / ".config/chromium",
    Path.home() / ".config/chromium-browser",
    Path.home() / ".config/microsoft-edge",
    Path.home() / ".var/app/com.google.Chrome/config/google-chrome",
    Path.home() / ".var/app/org.chromium.Chromium/config/chromium",
    Path.home() / "Library/Application Support/Google/Chrome",
    Path.home() / "Library/Application Support/Chromium",
)


class HumanProfileError(ValueError):
    """Refusing to use the interactive/human Chrome user-data-dir."""


def default_user_data_dir() -> Path:
    override = os.environ.get("CLAW_JEV_USER_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))
    return Path(xdg) / "norfront-claw" / "jev-chrome"


def chrome_binary() -> Path:
    override = os.environ.get("CLAW_JEV_CHROME", "").strip()
    candidates = [
        override,
        "/opt/google/chrome/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/local/bin/google-chrome",
        shutil.which("google-chrome") or "",
        shutil.which("google-chrome-stable") or "",
        shutil.which("chromium-browser") or "",
        shutil.which("chromium") or "",
    ]
    for raw in candidates:
        if not raw:
            continue
        path = Path(raw)
        if path.is_file() and os.access(path, os.X_OK):
            return path
    raise FileNotFoundError(
        "No Chrome/Chromium binary found. Set CLAW_JEV_CHROME or install Google Chrome."
    )


def assert_dedicated_profile(user_data_dir: Path) -> Path:
    resolved = user_data_dir.expanduser().resolve()
    for root in _DEFAULT_PROFILE_ROOTS:
        try:
            forbidden = root.resolve()
        except OSError:
            continue
        if resolved == forbidden or forbidden in resolved.parents:
            raise HumanProfileError(
                f"Refusing Chrome user-data-dir {resolved} (human/default profile {forbidden}). "
                "Point CLAW_JEV_USER_DATA_DIR at a dedicated directory."
            )
    return resolved


def use_no_sandbox() -> bool:
    """Linux cloud/containers usually cannot use chrome-sandbox. Opt out with CLAW_JEV_SANDBOX=1."""
    flag = os.environ.get("CLAW_JEV_SANDBOX", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return False
    flag = os.environ.get("CLAW_JEV_NO_SANDBOX", "").strip().lower()
    if flag in {"0", "false", "no"}:
        return False
    return os.name == "posix"


def use_headless() -> bool:
    flag = os.environ.get("CLAW_JEV_HEADLESS", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    if flag in {"0", "false", "no"}:
        return False
    return not os.environ.get("DISPLAY", "").strip()


def cdp_port() -> int:
    raw = os.environ.get("CLAW_JEV_CDP_PORT", "").strip()
    return int(raw) if raw else DEFAULT_CDP_PORT


def cdp_url(port: int | None = None) -> str:
    override = os.environ.get("CLAW_JEV_CDP_URL", "").strip()
    if override:
        return override.rstrip("/")
    return f"http://127.0.0.1:{port if port is not None else cdp_port()}"


def _chrome_child_env() -> dict[str, str]:
    """Chrome must not inherit API keys from the agent process."""
    env = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if upper.endswith(("_API_KEY", "_TOKEN")) or "PASSWORD" in upper or "SECRET" in upper:
            continue
        env[key] = value
    return env


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _json_version(url: str, timeout: float = 2.0) -> dict | None:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/json/version", timeout=timeout) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _pids_for_user_data_dir(user_data_dir: Path) -> list[int]:
    needle = str(user_data_dir)
    found: list[int] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return found
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmd = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "replace")
        except (OSError, PermissionError):
            continue
        if "chrome" in cmd.lower() and needle in cmd:
            found.append(int(entry.name))
    return found


def _wait_cdp(url: str, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = _json_version(url)
        if last:
            return last
        time.sleep(0.15)
    raise RuntimeError(f"Chrome CDP not reachable at {url} after {timeout:.0f}s")


class ChromeSession:
    """One dedicated-profile Chrome + browser-harness daemon named claw-jev."""

    def __init__(
        self,
        *,
        user_data_dir: Path | str | None = None,
        port: int | None = None,
        binary: Path | str | None = None,
    ):
        self.user_data_dir = assert_dedicated_profile(
            Path(user_data_dir) if user_data_dir else default_user_data_dir()
        )
        self.port = int(port) if port is not None else cdp_port()
        self.binary = Path(binary) if binary else chrome_binary()
        self.url = cdp_url(self.port)
        self.no_sandbox = use_no_sandbox()
        self.headless = use_headless()
        self.proc: subprocess.Popen | None = None

    def ensure(self) -> dict:
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        info = _json_version(self.url)
        ours = _pids_for_user_data_dir(self.user_data_dir)
        if info and ours:
            self._export_env()
            self._ensure_daemon()
            return info
        if info and not ours:
            raise RuntimeError(
                f"{self.url} is already a CDP endpoint but not our dedicated profile "
                f"{self.user_data_dir}. Set CLAW_JEV_CDP_PORT to a free port."
            )
        if _port_open(self.port) and not info:
            raise RuntimeError(f"127.0.0.1:{self.port} is taken by a non-CDP process")
        self._launch()
        info = _wait_cdp(self.url)
        self._export_env()
        self._ensure_daemon()
        return info

    def _launch(self) -> None:
        flags = [
            str(self.binary),
            f"--user-data-dir={self.user_data_dir}",
            f"--remote-debugging-port={self.port}",
            "--remote-debugging-address=127.0.0.1",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--disable-extensions",
            "--disable-popup-blocking",
            "--disable-background-networking",
            "--disable-features=Translate,MediaRouter",
            "--password-store=basic",
            "--use-mock-keychain",
            "--disable-dev-shm-usage",
            "--window-size=1120,780",
        ]
        if self.no_sandbox:
            flags[1:1] = ["--no-sandbox", "--disable-setuid-sandbox"]
        if self.headless:
            flags.append("--headless=new")
        flags.append("about:blank")
        log_path = self.user_data_dir / "claw-jev-chrome.log"
        log = log_path.open("ab")
        self.proc = subprocess.Popen(
            flags,
            stdout=log,
            stderr=log,
            env=_chrome_child_env(),
            start_new_session=True,
        )

    def _export_env(self) -> None:
        os.environ["BU_CDP_URL"] = self.url
        os.environ["BU_NAME"] = DAEMON_NAME
        os.environ.pop("BU_CDP_WS", None)

    def _ensure_daemon(self) -> None:
        from browser_harness.admin import ensure_daemon

        ensure_daemon(name=DAEMON_NAME)

    def stop(self) -> None:
        from browser_harness.admin import restart_daemon

        try:
            restart_daemon(DAEMON_NAME)
        except Exception:
            pass
        for pid in _pids_for_user_data_dir(self.user_data_dir):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                continue
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _pids_for_user_data_dir(self.user_data_dir):
            time.sleep(0.1)
        for pid in _pids_for_user_data_dir(self.user_data_dir):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        self.proc = None


_GLOBAL: ChromeSession | None = None


def global_session(**kwargs) -> ChromeSession:
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = ChromeSession(**kwargs)
    return _GLOBAL


def stop_chrome() -> None:
    session = _GLOBAL or ChromeSession()
    session.stop()


def doctor() -> dict:
    """Health for the core. Policy keys appear only as booleans."""
    from claw_jev.policy import policy_status

    user_data_dir = default_user_data_dir()
    profile_ok = True
    profile_error = None
    try:
        user_data_dir = assert_dedicated_profile(user_data_dir)
    except HumanProfileError as error:
        profile_ok = False
        profile_error = str(error)

    binary = None
    binary_error = None
    try:
        binary = str(chrome_binary())
    except FileNotFoundError as error:
        binary_error = str(error)

    url = cdp_url()
    info = _json_version(url)
    report = {
        "chrome_binary": binary,
        "chrome_binary_error": binary_error,
        "user_data_dir": str(user_data_dir),
        "user_data_dir_ok": profile_ok,
        "user_data_dir_error": profile_error,
        "human_profile_paths_blocked": [str(p) for p in _DEFAULT_PROFILE_ROOTS],
        "cdp_url": url,
        "cdp_ok": bool(info),
        "browser": (info or {}).get("Browser"),
        "protocol": (info or {}).get("Protocol-Version"),
        "daemon_name": DAEMON_NAME,
        "no_sandbox": use_no_sandbox(),
        "headless": use_headless(),
        "display": os.environ.get("DISPLAY") or None,
        "policy": policy_status(),
    }
    return report
