"""Official Linux installers. Noninteractive. Never print secrets."""

from __future__ import annotations

import os
import shutil
import subprocess

from .base import BrainError, BrainResult
from .paths import local_bin

GOOSE_INSTALL_URL = (
    "https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh"
)
OPENHANDS_INSTALL_URL = "https://install.openhands.dev/install.sh"
OPENCLAW_INSTALL_URL = "https://openclaw.ai/install.sh"
PRIME_HINT = (
    "Prime Agent is the default brain in product/claw. "
    "If that tree is present, run ./product/claw install. "
    "This package does not take Prime over."
)


def curl_pipe_sh(
    url: str,
    *,
    extra_env: dict[str, str] | None = None,
    timeout: int = 300,
    shell: str = "bash",
) -> BrainResult:
    curl = shutil.which("curl")
    if not curl:
        raise BrainError("curl is required to install a brain")
    local_bin().mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PATH"] = str(local_bin()) + os.pathsep + env.get("PATH", "")
    if extra_env:
        env.update(extra_env)
    script = subprocess.run(
        [
            curl,
            "--proto",
            "=https",
            "--tlsv1.2",
            "--proto-redir",
            "=https",
            "-fsSL",
            url,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    if script.returncode != 0:
        return BrainResult(
            ok=False,
            returncode=script.returncode,
            stdout=script.stdout or "",
            stderr=(script.stderr or "").strip()
            or f"failed to download installer (exit {script.returncode})",
            argv=(curl, "-fsSL", url),
        )
    installer = subprocess.run(
        [shell, "-s", "--"],
        input=script.stdout,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return BrainResult(
        ok=installer.returncode == 0,
        returncode=installer.returncode,
        stdout=installer.stdout or "",
        stderr=installer.stderr or "",
        argv=(shell, "-s", "--", url),
    )


def goose_install_env() -> dict[str, str]:
    return {
        "CONFIGURE": "false",
        "GOOSE_BIN_DIR": str(local_bin()),
        "GOOSE_DISABLE_KEYRING": "1",
    }


def openclaw_install_env() -> dict[str, str]:
    return {
        "OPENCLAW_NO_ONBOARD": "1",
        "OPENCLAW_NO_PROMPT": "1",
        "CI": "true",
        "OPENCLAW_INSTALL_METHOD": "npm",
    }


def which_after_install(name: str) -> str | None:
    path = local_bin() / name
    if path.exists():
        return str(path)
    return shutil.which(name)
