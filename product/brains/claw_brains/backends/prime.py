"""Prime Agent identity. Default brain; owned by product/claw. Probe + thin wrap."""

from __future__ import annotations

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
from ..config import Config
from ..install import PRIME_HINT

SPEC = BrainSpec(
    id="prime",
    name="Prime Agent",
    role="default",
    license="MIT",
    repo="https://github.com/PrimeIntellect-ai/prime-agent",
    binary_names=("prime-agent",),
    install_url="",
)


class PrimeBrain:
    spec = SPEC

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def which(self) -> str | None:
        return which_binary(self.cfg.prime_bin, self.spec.binary_names)

    def version(self) -> str | None:
        return probe_version(self.which())

    def doctor(self) -> BrainDoctor:
        binary = self.which()
        version = probe_version(binary)
        present = binary is not None
        keys = key_status(self.cfg, ("DEEPSEEK_API_KEY",))
        has_key = self.cfg.deepseek_key
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
                Check("deepseek", True, keys["DEEPSEEK_API_KEY"], warning=not has_key),
            ],
            stubbed=[] if (present and has_key) else ["live-model-turn"],
            install_hint=PRIME_HINT,
            license=self.spec.license,
            repo=self.spec.repo,
        )

    def print_argv(self, prompt: str) -> list[str]:
        binary = self.which()
        if not binary:
            raise FileNotFoundError("prime-agent is not on PATH")
        argv = [
            binary,
            "-p",
            "--mode",
            "json",
            "--provider",
            self.cfg.provider,
            "--model",
            self.cfg.model,
            "--no-session",
            "--cwd",
            str(self.cfg.workspace),
            "--no-context-files",
            "--",
            prompt,
        ]
        return refuse_secret_flags(argv)

    def run(self, prompt: str, *, timeout: int = 180) -> BrainResult:
        if not self.cfg.deepseek_key:
            return missing_key_stub(self.spec.id)
        if not self.which():
            return not_installed_stub(self.spec.id, PRIME_HINT)
        ensure_workspace(self.cfg)
        return run_argv(self.print_argv(prompt), cwd=self.cfg.workspace, timeout=timeout)

    def install(self, *, timeout: int = 300) -> BrainResult:
        del timeout
        return BrainResult(
            ok=True,
            returncode=0,
            stdout=PRIME_HINT + "\n",
            stderr="",
            stubbed=True,
            reason="owned-by-claw",
        )
