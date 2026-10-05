"""Prime Agent as the Norfront Claw brain. Subprocess wrapper; not a VM computer."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .browser import jev_skill_dir
from .config import Config
from .paths import product_dir

INSTALL_URL = "https://app.primeintellect.ai/prime-agent/install.sh"
DEFAULT_PROMPT_NAME = "prime-prompt.md"


class BrainError(RuntimeError):
    pass


class MissingApiKey(BrainError):
    pass


@dataclass
class BrainResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    argv: tuple[str, ...]


class PrimeBrain:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.binary = cfg.prime_bin

    def which(self) -> str | None:
        if os.path.sep in self.binary:
            path = Path(self.binary).expanduser()
            return str(path) if path.exists() else None
        found = shutil.which(self.binary)
        if found:
            return found
        home = Path.home() / ".local" / "bin" / "prime-agent"
        return str(home) if home.exists() else None

    def resolved(self) -> str:
        path = self.which()
        if not path:
            raise BrainError(
                "prime-agent is not on PATH. Run: ./product/claw install"
            )
        return path

    def version(self) -> str | None:
        binary = self.which()
        if not binary:
            return None
        try:
            proc = subprocess.run(
                [binary, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        text = (proc.stdout or proc.stderr or "").strip()
        return text.splitlines()[0] if text else None

    def system_prompt(self) -> str:
        path = product_dir(self.cfg.repo_root) / DEFAULT_PROMPT_NAME
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return (
            "You are the Norfront Claw brain (Prime Agent). "
            "Do not take irreversible actions (send, post, pay, delete, sign up) "
            "without an explicit operator allow. Never print secrets."
        )

    def print_argv(self, prompt: str, *, json_mode: bool = True) -> list[str]:
        """Build a headless Prime Agent argv. Never put API keys on the command line."""
        binary = self.resolved()
        argv = [binary, "-p"]
        if json_mode:
            argv += ["--mode", "json"]
        argv += [
            "--provider",
            self.cfg.provider,
            "--model",
            self.cfg.model,
            "--no-session",
            "--cwd",
            str(self.cfg.workspace),
            "--no-context-files",
            "--append-system-prompt",
            self.system_prompt(),
        ]
        skill = jev_skill_dir(self.cfg.repo_root)
        extra = os.environ.get("CLAW_PRIME_SKILL")
        if extra:
            argv += ["--skill", extra]
        elif skill is not None:
            argv += ["--skill", str(skill)]
        argv += ["--", prompt]
        if any(flag == "--api-key" for flag in argv):
            raise BrainError("internal error: refusing to put --api-key on argv")
        return argv

    def ensure_workspace(self) -> Path:
        self.cfg.workspace.mkdir(parents=True, exist_ok=True)
        return self.cfg.workspace

    def run_print(self, prompt: str, *, timeout: int = 180) -> BrainResult:
        if not self.cfg.deepseek_key and self.cfg.provider == "deepseek":
            raise MissingApiKey(
                "DEEPSEEK_API_KEY is missing. Put it in claw.env locally "
                "(not in chat), then re-run."
            )
        argv = self.print_argv(prompt)
        self.ensure_workspace()
        env = os.environ.copy()
        local_bin = str(Path.home() / ".local" / "bin")
        env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")
        if self.cfg.session_dir is not None:
            env["PRIME_AGENT_SESSION_DIR"] = str(self.cfg.session_dir)
        proc = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(self.cfg.workspace),
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0 and "No API key found" in combined:
            raise MissingApiKey(
                "Prime Agent found no API key for the selected model. "
                "Put DEEPSEEK_API_KEY in claw.env locally, not in chat."
            )
        return BrainResult(
            ok=proc.returncode == 0,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            argv=tuple(argv),
        )

    def _cli(self, args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        binary = self.resolved()
        env = os.environ.copy()
        local_bin = str(Path.home() / ".local" / "bin")
        env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")
        return subprocess.run(
            [binary, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

    def status_text(self) -> str:
        proc = self._cli(["status"])
        return (proc.stdout or proc.stderr or "").strip() or "prime-agent status produced no output"

    def shutdown(self) -> str:
        proc = self._cli(["shutdown", "--force"])
        return (proc.stdout or proc.stderr or "").strip() or "shutdown requested"

    def list_agents(self) -> str:
        proc = self._cli(["list"])
        return (proc.stdout or proc.stderr or "").strip()


def install_prime_agent(*, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    """Official native installer. Noninteractive; bootstraps the Python kernel.

    `timeout` is the whole download plus install, not each step on its own.
    """
    import time

    env = os.environ.copy()
    env["PRIME_AGENT_INSTALLER_NONINTERACTIVE"] = "1"
    env["PRIME_AGENT_BOOTSTRAP_KERNEL_ON_INSTALL"] = "1"
    curl = shutil.which("curl")
    if not curl:
        raise BrainError("curl is required to install prime-agent")
    deadline = time.monotonic() + timeout

    def remaining() -> float:
        left = deadline - time.monotonic()
        if left <= 0:
            raise subprocess.TimeoutExpired("prime-agent", timeout)
        return left

    script = subprocess.run(
        [
            curl,
            "--proto",
            "=https",
            "--proto-redir",
            "=https",
            "-fsSL",
            INSTALL_URL,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=remaining(),
        env=env,
    )
    if script.returncode != 0:
        raise BrainError(
            f"failed to download Prime Agent installer (exit {script.returncode})"
        )
    installer = subprocess.run(
        ["sh", "-s"],
        input=script.stdout,
        check=False,
        capture_output=True,
        text=True,
        timeout=remaining(),
        env=env,
    )
    return installer
