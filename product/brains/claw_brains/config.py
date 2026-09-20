"""Load config from the environment. Never store or print secret values."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .paths import brains_home, repo_root, xdg_data_home

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
        "LLM_API_KEY",
        "TAVILY_API_KEY",
        "EXA_API_KEY",
        "FIRECRAWL_API_KEY",
        "GOOSE_PROVIDER__API_KEY",
    }
)

STORED_IN_HERMES = "__stored_in_hermes__"
_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
KNOWN_BRAINS = ("prime", "openhands", "openclaw", "goose")
DEFAULT_BRAIN = "prime"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_PROVIDER = "deepseek"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


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
    """Fill os.environ from files for keys that are not already set."""
    loaded: list[Path] = []
    files = [
        root / "product" / "brains" / ".env",
        root / "product" / ".env",
        root / "claw.env",
    ]
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


def presence_label(set_: bool) -> str:
    return "set" if set_ else "missing"


@dataclass(frozen=True)
class Config:
    repo_root: Path
    env_files: tuple[Path, ...]
    provider: str
    model: str
    workspace: Path
    brains_home: Path
    brain_env: str
    prime_bin: str
    openhands_bin: str
    openclaw_bin: str
    goose_bin: str
    deepseek_key: bool
    openai_key: bool
    llm_api_key: bool
    extra: dict[str, str] = field(default_factory=dict, repr=False, compare=False)

    def __repr__(self) -> str:
        return (
            f"Config(repo_root={self.repo_root!s}, provider={self.provider!r}, "
            f"model={self.model!r}, brain_env={self.brain_env!r}, "
            f"deepseek_key={'set' if self.deepseek_key else 'missing'}, "
            f"openai_key={'set' if self.openai_key else 'missing'}, "
            f"llm_api_key={'set' if self.llm_api_key else 'missing'})"
        )

    def has_model_key(self) -> bool:
        return self.deepseek_key or self.openai_key or self.llm_api_key


def load_config(root: Path | None = None) -> Config:
    root = (root or repo_root()).resolve()
    env_files = tuple(load_env_files(root))
    data = xdg_data_home() / "norfront-claw"
    workspace = Path(
        os.environ.get("CLAW_WORKSPACE") or str(data / "workspace")
    ).expanduser()
    home = Path(os.environ.get("CLAW_BRAINS_HOME") or str(brains_home())).expanduser()
    return Config(
        repo_root=root,
        env_files=env_files,
        provider=os.environ.get("CLAW_PROVIDER") or DEFAULT_PROVIDER,
        model=os.environ.get("CLAW_MODEL") or DEFAULT_MODEL,
        workspace=workspace,
        brains_home=home,
        brain_env=(os.environ.get("CLAW_BRAIN") or "").strip().lower(),
        prime_bin=os.environ.get("CLAW_PRIME_BIN") or "prime-agent",
        openhands_bin=os.environ.get("CLAW_OPENHANDS_BIN") or "openhands",
        openclaw_bin=os.environ.get("CLAW_OPENCLAW_BIN") or "openclaw",
        goose_bin=os.environ.get("CLAW_GOOSE_BIN") or "goose",
        deepseek_key=secret_is_set("DEEPSEEK_API_KEY"),
        openai_key=secret_is_set("OPENAI_API_KEY"),
        llm_api_key=secret_is_set("LLM_API_KEY"),
    )
