"""Goose (AAIF) Linux CLI. Model-agnostic runtime; not a VM computer."""

from __future__ import annotations

import os

from ..base import (
    BrainDoctor,
    BrainResult,
    BrainSpec,
    Check,
    ensure_workspace,
    key_status,
    live_turn_state,
    missing_key_stub,
    not_installed_stub,
    probe_version,
    refuse_secret_flags,
    run_argv,
    which_binary,
)
from ..config import DEEPSEEK_BASE_URL, Config
from ..install import GOOSE_INSTALL_URL, curl_pipe_sh, goose_install_env

SPEC = BrainSpec(
    id="goose",
    name="Goose",
    role="optional",
    license="Apache-2.0",
    repo="https://github.com/aaif-goose/goose",
    binary_names=("goose",),
    install_url=GOOSE_INSTALL_URL,
    isolation=(
        "Host process (goose CLI). No VM computers. Pair with product/vm for R2. "
        "Headless runs set GOOSE_DISABLE_KEYRING=1."
    ),
)

HINT = "Install: ./product/brains/claw-brains install goose"


class GooseBrain:
    spec = SPEC

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def which(self) -> str | None:
        return which_binary(self.cfg.goose_bin, self.spec.binary_names)

    def version(self) -> str | None:
        return probe_version(self.which())

    def _has_key(self) -> bool:
        return self.cfg.deepseek_key or self.cfg.openai_key

    def doctor(self) -> BrainDoctor:
        binary = self.which()
        version = self.version()
        present = binary is not None
        keys = key_status(self.cfg, ("DEEPSEEK_API_KEY", "OPENAI_API_KEY"))
        has_key = self._has_key()
        return BrainDoctor(
            id=self.spec.id,
            name=self.spec.name,
            role=self.spec.role,
            present=present,
            version=version,
            binary=binary,
            keys=keys,
            live_turn=live_turn_state(present=present, has_key=has_key),
            isolation=self.spec.isolation,
            checks=[
                Check("binary", present, binary or "not on PATH", warning=not present),
                Check("version", version is not None, version or "unknown", warning=not present),
                Check("model-key", True, "set" if has_key else "missing", warning=not has_key),
            ],
            stubbed=[] if (present and has_key) else ["live-model-turn"],
            install_hint=HINT,
            license=self.spec.license,
            repo=self.spec.repo,
        )

    def print_argv(self, prompt: str) -> list[str]:
        binary = self.which()
        if not binary:
            raise FileNotFoundError("goose is not on PATH")
        argv = [
            binary,
            "run",
            "--no-session",
            "--output-format",
            "json",
            "-t",
            prompt,
        ]
        return refuse_secret_flags(argv)

    def _child_env(self) -> dict[str, str]:
        extra = {
            "GOOSE_DISABLE_KEYRING": os.environ.get("GOOSE_DISABLE_KEYRING") or "1",
            "GOOSE_MODEL": os.environ.get("GOOSE_MODEL") or self.cfg.model,
        }
        if os.environ.get("GOOSE_PROVIDER"):
            extra["GOOSE_PROVIDER"] = os.environ["GOOSE_PROVIDER"]
        elif self.cfg.provider == "deepseek":
            extra["GOOSE_PROVIDER"] = "openai"
        else:
            extra["GOOSE_PROVIDER"] = self.cfg.provider
        if not os.environ.get("OPENAI_API_KEY") and os.environ.get("DEEPSEEK_API_KEY"):
            extra["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]
            extra.setdefault(
                "OPENAI_BASE_URL",
                os.environ.get("OPENAI_BASE_URL") or DEEPSEEK_BASE_URL,
            )
        elif extra.get("GOOSE_PROVIDER") == "openai":
            extra.setdefault(
                "OPENAI_BASE_URL",
                os.environ.get("OPENAI_BASE_URL") or DEEPSEEK_BASE_URL,
            )
        return extra

    def run(self, prompt: str, *, timeout: int = 180) -> BrainResult:
        if not self._has_key():
            return missing_key_stub(self.spec.id)
        if not self.which():
            return not_installed_stub(self.spec.id, HINT)
        ensure_workspace(self.cfg)
        return run_argv(
            self.print_argv(prompt),
            cwd=self.cfg.workspace,
            timeout=timeout,
            extra_env=self._child_env(),
        )

    def install(self, *, timeout: int = 300) -> BrainResult:
        return curl_pipe_sh(
            GOOSE_INSTALL_URL,
            extra_env=goose_install_env(),
            timeout=timeout,
            shell="bash",
        )
