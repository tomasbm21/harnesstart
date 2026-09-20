"""OpenHands Linux CLI. Native binary; Docker sandbox is optional and not used here."""

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
from ..install import OPENHANDS_INSTALL_URL, curl_pipe_sh

SPEC = BrainSpec(
    id="openhands",
    name="OpenHands",
    role="optional",
    license="MIT",
    repo="https://github.com/OpenHands/OpenHands",
    binary_names=("openhands",),
    install_url=OPENHANDS_INSTALL_URL,
    isolation=(
        "Host process (OpenHands CLI). Default upstream sandbox is Docker; "
        "this adapter does not start Docker. Pair with product/vm for R2."
    ),
)

HINT = "Install: ./product/brains/claw-brains install openhands"


class OpenHandsBrain:
    spec = SPEC

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def which(self) -> str | None:
        return which_binary(self.cfg.openhands_bin, self.spec.binary_names)

    def version(self) -> str | None:
        return probe_version(self.which(), ("-v",)) or probe_version(self.which())

    def _has_key(self) -> bool:
        return self.cfg.llm_api_key or self.cfg.deepseek_key

    def doctor(self) -> BrainDoctor:
        binary = self.which()
        version = self.version()
        present = binary is not None
        keys = key_status(self.cfg, ("DEEPSEEK_API_KEY", "LLM_API_KEY"))
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
                Check("llm-key", True, "set" if has_key else "missing", warning=not has_key),
            ],
            stubbed=[] if (present and has_key) else ["live-model-turn"],
            install_hint=HINT,
            license=self.spec.license,
            repo=self.spec.repo,
        )

    def print_argv(self, prompt: str) -> list[str]:
        binary = self.which()
        if not binary:
            raise FileNotFoundError("openhands is not on PATH")
        argv = [
            binary,
            "--headless",
            "--json",
            "--override-with-envs",
            "-t",
            prompt,
        ]
        return refuse_secret_flags(argv)

    def _child_env(self) -> dict[str, str]:
        extra: dict[str, str] = {}
        if not os.environ.get("LLM_API_KEY") and os.environ.get("DEEPSEEK_API_KEY"):
            extra["LLM_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]
        extra.setdefault("LLM_MODEL", os.environ.get("LLM_MODEL") or f"deepseek/{self.cfg.model}")
        extra.setdefault("LLM_BASE_URL", os.environ.get("LLM_BASE_URL") or DEEPSEEK_BASE_URL)
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
        return curl_pipe_sh(OPENHANDS_INSTALL_URL, timeout=timeout, shell="sh")
