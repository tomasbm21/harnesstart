"""Load config from the environment. Never store or print secret values."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .paths import product_dir, repo_root, xdg_data_home

# Values that look like secrets must never appear in logs, doctor output, or repr.
SECRET_KEYS = frozenset(
    {
        "DEEPSEEK_API_KEY",
        "WEB_API_KEY",
        "GH_TOKEN",
        "CLAW_JUDGE_API_KEY",
        "TYPESAFE_API_KEY",
        "TEXT_MODEL_API_KEY",
        "BROWSER_USE_API_KEY",
        "PRIME_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "TAVILY_API_KEY",
        "EXA_API_KEY",
        "FIRECRAWL_API_KEY",
    }
)

STORED_IN_HERMES = "__stored_in_hermes__"
_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _strip_value(raw: str) -> str:
    val = re.sub(r"\s+#.*$", "", raw).strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in {'"', "'"}:
        val = val[1:-1]
    return val


def parse_env_file(path: Path) -> dict[str, str]:
    """Read KEY=VALUE lines without executing the file."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, rest = line.partition("=")
        key = key.strip()
        if not _KEY_RE.match(key):
            continue
        out[key] = _strip_value(rest)
    return out


def is_present(value: str | None) -> bool:
    if not value:
        return False
    return value != STORED_IN_HERMES


def load_env_files(root: Path) -> list[Path]:
    """Fill os.environ from files for keys that are not already set.

    Existing process environment wins so operators can export a key without
    putting it in a file. File order: product/.env then repo claw.env
    (claw.env wins over product/.env when both set a missing key).
    """
    loaded: list[Path] = []
    files = [product_dir(root) / ".env", root / "claw.env"]
    # Later files override earlier ones, but never override a non-empty process env.
    merged: dict[str, str] = {}
    for path in files:
        parsed = parse_env_file(path)
        if parsed:
            loaded.append(path)
            merged.update(parsed)
    for key, value in merged.items():
        current = os.environ.get(key)
        if current is None or current == "":
            os.environ[key] = value
    return loaded


def secret_is_set(name: str) -> bool:
    return is_present(os.environ.get(name))


@dataclass(frozen=True)
class Config:
    repo_root: Path
    env_files: tuple[Path, ...]
    provider: str
    model: str
    prime_bin: str
    workspace: Path
    browser_profile: Path
    cdp_url: str
    display: str
    browser_adapter_spec: str
    allow_irreversible: bool
    deepseek_key: bool
    typesafe_key: bool
    text_model_key: bool
    web_api_key: bool
    gh_token: bool
    web_backend: str
    chrome_no_sandbox: bool
    session_dir: Path | None = None
    extra: dict[str, str] = field(default_factory=dict, repr=False, compare=False)

    def __repr__(self) -> str:
        return (
            f"Config(repo_root={self.repo_root!s}, provider={self.provider!r}, "
            f"model={self.model!r}, prime_bin={self.prime_bin!r}, "
            f"deepseek_key={'set' if self.deepseek_key else 'missing'}, "
            f"typesafe_key={'set' if self.typesafe_key else 'missing'}, "
            f"text_model_key={'set' if self.text_model_key else 'missing'})"
        )


def load_config(root: Path | None = None) -> Config:
    root = (root or repo_root()).resolve()
    env_files = tuple(load_env_files(root))
    data = xdg_data_home() / "norfront-claw"
    workspace = Path(
        os.environ.get("CLAW_WORKSPACE") or str(data / "workspace")
    ).expanduser()
    profile = Path(
        os.environ.get("CLAW_BROWSER_PROFILE") or str(data / "chrome-profile")
    ).expanduser()
    session = os.environ.get("PRIME_AGENT_SESSION_DIR") or os.environ.get(
        "CLAW_SESSION_DIR"
    )
    return Config(
        repo_root=root,
        env_files=env_files,
        provider=os.environ.get("CLAW_PROVIDER") or "deepseek",
        model=os.environ.get("CLAW_MODEL") or "deepseek-v4-pro",
        prime_bin=os.environ.get("CLAW_PRIME_BIN") or "prime-agent",
        workspace=workspace,
        browser_profile=profile,
        cdp_url=os.environ.get("BU_CDP_URL") or os.environ.get("CLAW_CDP_URL") or "",
        display=os.environ.get("DISPLAY") or "",
        browser_adapter_spec=os.environ.get("CLAW_BROWSER_ADAPTER") or "",
        allow_irreversible=_truthy(os.environ.get("CLAW_ALLOW_IRREVERSIBLE")),
        deepseek_key=secret_is_set("DEEPSEEK_API_KEY"),
        typesafe_key=secret_is_set("TYPESAFE_API_KEY"),
        text_model_key=secret_is_set("TEXT_MODEL_API_KEY") or secret_is_set("DEEPSEEK_API_KEY"),
        web_api_key=secret_is_set("WEB_API_KEY"),
        gh_token=secret_is_set("GH_TOKEN"),
        web_backend=os.environ.get("WEB_BACKEND") or "",
        chrome_no_sandbox=_chrome_no_sandbox(),
        session_dir=Path(session).expanduser() if session else None,
    )


def _truthy(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _chrome_no_sandbox() -> bool:
    raw = os.environ.get("CLAW_CHROME_NO_SANDBOX")
    if raw is None or raw == "":
        # Cloud/nested Linux Chrome usually needs this; Jev adapter reads the flag.
        return True
    return _truthy(raw)


def presence_label(set_: bool) -> str:
    return "set" if set_ else "missing"
