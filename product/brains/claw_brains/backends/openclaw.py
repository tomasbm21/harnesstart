"""OpenClaw gateway/brain. Isolate it; default upstream tools run on the host."""

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
from ..install import (
    OPENCLAW_INSTALL_URL,
    curl_pipe_sh,
    openclaw_install_env,
    promote_to_local_bin,
)

SPEC = BrainSpec(
    id="openclaw",
    name="OpenClaw",
    role="optional",
    license="MIT",
    repo="https://github.com/openclaw/openclaw",
    binary_names=("openclaw",),
    install_url=OPENCLAW_INSTALL_URL,
    isolation=(
        "Host tools by default (BRIEF R2 fail unless paired with product/vm). "
        "This adapter uses `openclaw agent exec --auth-env-only` (no Gateway daemon)."
    ),
)

HINT = "Install: ./product/brains/claw-brains install openclaw"


def node_report() -> tuple[bool, str]:
    """OpenClaw wants Node 24.16+ or 26.1+. This cloud image ships Node 22 on PATH."""
    import shutil
    import subprocess

    from ..base import _child_env
    from ..paths import nvm_bin_dirs

    candidates: list[str] = []
    for directory in nvm_bin_dirs():
        candidate = directory / "node"
        if candidate.exists():
            candidates.append(str(candidate))
    which = shutil.which("node")
    if which and which not in candidates:
        candidates.append(which)
    if not candidates:
        return False, "node not found (OpenClaw needs 24.16+ or 26.1+)"

    last = "node not found"
    for node in candidates:
        try:
            proc = subprocess.run(
                [node, "-v"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                env=_child_env(),
            )
        except (OSError, subprocess.TimeoutExpired):
            last = f"{node} (version probe failed)"
            continue
        raw = (proc.stdout or proc.stderr or "").strip().lstrip("v")
        parts = raw.split(".")
        try:
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            last = f"{node} {raw}"
            continue
        ok = (major == 24 and minor >= 16) or major >= 26
        detail = f"{node} v{raw}"
        if ok:
            return True, detail
        last = detail + " (OpenClaw needs 24.16+ or 26.1+)"
    return False, last


class OpenClawBrain:
    spec = SPEC

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def which(self) -> str | None:
        return which_binary(self.cfg.openclaw_bin, self.spec.binary_names)

    def version(self) -> str | None:
        return probe_version(self.which(), ("-V",)) or probe_version(self.which())

    def _has_key(self) -> bool:
        return self.cfg.deepseek_key or self.cfg.openai_key

    def doctor(self) -> BrainDoctor:
        binary = self.which()
        version = self.version()
        present = binary is not None
        keys = key_status(self.cfg, ("DEEPSEEK_API_KEY", "OPENAI_API_KEY"))
        has_key = self._has_key()
        node_ok, node_detail = node_report()
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
                Check(
                    "node",
                    True,
                    node_detail,
                    warning=not node_ok,
                ),
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
            raise FileNotFoundError("openclaw is not on PATH")
        model = self.cfg.model
        if "/" not in model:
            model = f"{self.cfg.provider}/{model}"
        argv = [
            binary,
            "agent",
            "exec",
            "--auth-env-only",
            "--json",
            "--cwd",
            str(self.cfg.workspace),
            "--model",
            model,
            prompt,
        ]
        return refuse_secret_flags(argv)

    def run(self, prompt: str, *, timeout: int = 180) -> BrainResult:
        if not self._has_key():
            return missing_key_stub(self.spec.id)
        if not self.which():
            return not_installed_stub(self.spec.id, HINT)
        ensure_workspace(self.cfg)
        return run_argv(self.print_argv(prompt), cwd=self.cfg.workspace, timeout=timeout)

    def install(self, *, timeout: int = 420) -> BrainResult:
        result = curl_pipe_sh(
            OPENCLAW_INSTALL_URL,
            extra_env=openclaw_install_env(),
            timeout=timeout,
            shell="bash",
        )
        if result.ok:
            promote_to_local_bin("openclaw", self.which())
        return result
