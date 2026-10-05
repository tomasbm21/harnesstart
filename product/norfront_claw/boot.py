"""One boot for the whole app. Install what is missing, start the console, keep going."""

from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .brain import PrimeBrain, install_prime_agent
from .config import load_config
from .doctor import report
from .paths import repo_root, xdg_data_home
from .prompt_keys import ensure_boot_keys, stdin_is_tty
from .secrets import redact

CONSOLE_URL = "http://127.0.0.1:5173"
CONSOLE_PORT = 5173
NODE_VERSION = "v22.19.0"


@dataclass
class BootHooks:
    port_open: object
    ensure_node: object
    install_console: object
    ensure_prime: object
    ensure_jev: object
    refresh: object
    start_console: object
    open_browser: object
    wait: object
    ready: object
    interactive: object = None


def plain_notes(snapshot: dict, extra: list[str] | None = None) -> list[str]:
    """Sentences for the console. No shell commands."""
    notes: list[str] = []
    vm = snapshot.get("vm") if isinstance(snapshot.get("vm"), dict) else {}
    if not vm.get("r2_hardware_kvm"):
        notes.append(
            "Hardware KVM is not available on this machine. The app stays up, and QEMU stays the computer."
        )
    keys = snapshot.get("keys") if isinstance(snapshot.get("keys"), dict) else {}
    if keys.get("TYPESAFE_API_KEY") != "set":
        notes.append("Live browser actions need a TypeSafe key. Looking at a page still works.")
    notes.append("The crew is in this window. Type a task at the top.")
    for item in extra or []:
        sentence = " ".join(str(item).split())
        if not sentence or "./" in sentence or "npm " in sentence or "claw-brains" in sentence:
            continue
        if sentence not in notes:
            notes.append(sentence[:240])
    return notes


def port_open(port: int = CONSOLE_PORT) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def state_dir() -> Path:
    path = xdg_data_home() / "norfront-claw" / "boot"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _lock_path() -> Path:
    return state_dir() / "boot.lock"


def _read_lock_pid() -> int | None:
    path = _lock_path()
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw.isdigit():
        return None
    return int(raw)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def claim_boot() -> str:
    """Return 'held', 'busy', or 'clear'. Never steals a live boot."""
    path = _lock_path()
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        pid = _read_lock_pid()
        if pid is not None and _pid_alive(pid):
            return "busy"
        if port_open():
            return "busy"
        try:
            path.unlink()
        except OSError:
            return "busy"
        return claim_boot()
    os.write(fd, str(os.getpid()).encode("utf-8"))
    os.close(fd)
    return "held"


def release_boot() -> None:
    path = _lock_path()
    pid = _read_lock_pid()
    if pid == os.getpid():
        try:
            path.unlink()
        except OSError:
            return


def node_archive(system: str, machine: str) -> tuple[str, str] | None:
    arch = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(
        machine.lower()
    )
    if arch is None:
        return None
    if system == "win32":
        name = f"node-{NODE_VERSION}-win-{arch}"
        return name, f"https://nodejs.org/dist/{NODE_VERSION}/{name}.zip"
    if system == "linux":
        name = f"node-{NODE_VERSION}-linux-{arch}"
        return name, f"https://nodejs.org/dist/{NODE_VERSION}/{name}.tar.xz"
    return None


def install_node(dest: Path, *, opener=None) -> Path | None:
    """Download a user-local Node if `node` is not already on PATH."""
    if shutil.which("node") and shutil.which("npm"):
        return Path(shutil.which("node") or "")
    spec = node_archive(sys.platform, platform.machine())
    if spec is None:
        return None
    name, url = spec
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / (name + (".zip" if url.endswith(".zip") else ".tar.xz"))
    fetch = opener or urllib.request.urlopen
    try:
        with fetch(url, timeout=60) as response:
            archive.write_bytes(response.read())
        if url.endswith(".zip"):
            with zipfile.ZipFile(archive) as packed:
                packed.extractall(dest)
        else:
            with tarfile.open(archive, "r:xz") as packed:
                packed.extractall(dest)
    except (OSError, tarfile.TarError, zipfile.BadZipFile, TimeoutError):
        return None
    bin_dir = dest / name if sys.platform == "win32" else dest / name / "bin"
    node = bin_dir / ("node.exe" if sys.platform == "win32" else "node")
    if not node.is_file():
        return None
    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    return node


def install_console(ui_dir: Path) -> None:
    if (ui_dir / "node_modules").is_dir():
        return
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm missing")
    subprocess.run(
        [npm, "install"],
        cwd=ui_dir,
        check=True,
        timeout=300,
        capture_output=True,
        text=True,
    )


def ensure_prime(cfg) -> str:
    if PrimeBrain(cfg).which():
        return ""
    try:
        install_prime_agent(timeout=180)
    except Exception:
        return "The brain program is not installed. The console, checks, and crew still run."
    if PrimeBrain(cfg).which():
        return ""
    return "The brain program is not installed. The console, checks, and crew still run."


def ensure_jev(root: Path) -> str:
    jev = root / "product" / "jev"
    if (jev / ".venv").is_dir():
        return ""
    if not jev.is_dir():
        return "The browser package is not on this checkout. Looking at a page from the console still works."
    uv = shutil.which("uv")
    try:
        if uv:
            proc = subprocess.run(
                [uv, "sync", "--extra", "dev"],
                cwd=jev,
                check=False,
                timeout=180,
                capture_output=True,
                text=True,
            )
            if proc.returncode == 0:
                return ""
        pip = shutil.which("pip") or shutil.which("pip3")
        if pip:
            proc = subprocess.run(
                [pip, "install", "-e", str(jev)],
                cwd=root,
                check=False,
                timeout=180,
                capture_output=True,
                text=True,
            )
            if proc.returncode == 0:
                return ""
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "The browser package is not installed. Looking at a page from the console still works."


def refresh_status(root: Path, *, no_prompt: bool, extra: list[str]) -> dict:
    from importlib.util import module_from_spec, spec_from_file_location

    writer_path = root / "product" / "ui" / "write_status.py"
    spec = spec_from_file_location("claw_ui_write_status", writer_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("status writer missing")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    cfg = ensure_boot_keys(load_config(root), command="doctor", no_prompt=no_prompt)
    snapshot = module.project_snapshot(report(cfg))
    snapshot["boot"] = {"notes": plain_notes(snapshot, extra)}
    module.assert_clean(snapshot)
    out = root / "product" / "ui" / "public" / "status.local.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    import json

    out.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return snapshot


def terminate_console(proc) -> None:
    """Stop the console server and its children.

    `npm run dev` is a .cmd shim that spawns node, so on Windows terminating
    just the shim orphans the server (the port stays busy and the next launch
    thinks the app is still up). Kill the whole tree instead.
    """
    try:
        if sys.platform == "win32":
            pid = getattr(proc, "pid", None)
            if pid:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    check=False,
                )
                return
        proc.terminate()
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


def start_console(ui_dir: Path) -> subprocess.Popen[str]:
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm missing")
    # The dev server must NOT share the launch window's stdin: Vite reads the
    # terminal for its own h/r/q shortcuts, which would swallow whatever the
    # operator types at the claw> prompt. Its logs go to a file instead so they
    # do not scribble over the prompt either.
    log_path = state_dir() / "console.log"
    sink = open(log_path, "ab", buffering=0)
    return subprocess.Popen(
        [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(CONSOLE_PORT), "--strictPort"],
        cwd=ui_dir,
        stdin=subprocess.DEVNULL,
        stdout=sink,
        stderr=sink,
    )


def open_browser(url: str = CONSOLE_URL) -> None:
    if sys.platform == "win32":
        os.startfile(url)  # type: ignore[attr-defined]
        return
    opener = shutil.which("xdg-open") or shutil.which("open")
    if opener:
        subprocess.Popen([opener, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    print(url)


def wait_for_port(seconds: float = 40) -> bool:
    import time

    deadline = time.time() + seconds
    while time.time() < deadline:
        if port_open():
            return True
        time.sleep(0.5)
    return False


def run_boot(hooks: BootHooks) -> int:
    if hooks.port_open():
        hooks.refresh(True)
        print("Norfront Claw is already running.")
        print(CONSOLE_URL)
        hooks.open_browser()
        return 0
    claim = claim_boot()
    if claim == "busy":
        print("Norfront Claw is already starting.")
        print(CONSOLE_URL)
        hooks.open_browser()
        return 0
    extra: list[str] = []
    try:
        node = hooks.ensure_node()
        if not node:
            extra.append("Node did not install. The console cannot open. The checks still ran.")
        else:
            try:
                hooks.install_console()
            except Exception:
                extra.append("The console files did not install. The checks still ran.")
                node = None
        prime_note = hooks.ensure_prime()
        jev_note = hooks.ensure_jev()
        if prime_note:
            extra.append(prime_note)
        if jev_note:
            extra.append(jev_note)
        hooks.refresh(False, extra)
        if not node:
            print("Norfront Claw checks finished. The console could not start.")
            return 0
        if hooks.port_open():
            print("Norfront Claw is already running.")
            print(CONSOLE_URL)
            hooks.open_browser()
            return 0
        proc = hooks.start_console()
        if not hooks.ready():
            print("The console did not answer. The checks still ran.")
            terminate_console(proc)
            return 0
        print("Norfront Claw is running.")
        print("Leave this window open. Close it to stop.")
        print(CONSOLE_URL)
        hooks.open_browser()
        if hooks.interactive is not None and stdin_is_tty():
            return int(hooks.interactive(proc))
        return int(hooks.wait(proc))
    finally:
        release_boot()


def default_hooks(root: Path) -> BootHooks:
    ui = root / "product" / "ui"

    def ensure_node():
        return install_node(state_dir() / "node")

    def install_ui():
        install_console(ui)

    def prime():
        return ensure_prime(load_config(root))

    def jev():
        return ensure_jev(root)

    def refresh(no_prompt: bool, extra: list[str] | None = None):
        return refresh_status(root, no_prompt=no_prompt, extra=extra or [])

    def start():
        return start_console(ui)

    def wait(proc: subprocess.Popen[str]) -> int:
        try:
            return proc.wait()
        except KeyboardInterrupt:
            terminate_console(proc)
            return 0

    def interactive(proc: subprocess.Popen[str]) -> int:
        from .repl import run_repl

        def stop() -> None:
            terminate_console(proc)

        return run_repl(root, stop=stop)

    return BootHooks(
        port_open=port_open,
        ensure_node=ensure_node,
        install_console=install_ui,
        ensure_prime=prime,
        ensure_jev=jev,
        refresh=refresh,
        start_console=start,
        open_browser=open_browser,
        wait=wait,
        ready=wait_for_port,
        interactive=interactive,
    )


def main() -> int:
    root = repo_root()
    os.environ.setdefault("CLAW_REPO", str(root))
    print(redact("Norfront Claw is starting."))
    return run_boot(default_hooks(root))


if __name__ == "__main__":
    raise SystemExit(main())
