"""Select and load brains. Prime is the default; CLAW_BRAIN env wins."""

from __future__ import annotations

from .backends.goose import GooseBrain
from .backends.openclaw import OpenClawBrain
from .backends.openhands import OpenHandsBrain
from .backends.prime import PrimeBrain
from .base import Brain, UnknownBrain
from .config import DEFAULT_BRAIN, KNOWN_BRAINS, Config, load_config
from .paths import brains_home, selected_path

_FACTORIES = {
    "prime": PrimeBrain,
    "openhands": OpenHandsBrain,
    "openclaw": OpenClawBrain,
    "goose": GooseBrain,
}


def normalize_id(raw: str | None) -> str:
    if not raw:
        return DEFAULT_BRAIN
    value = raw.strip().lower()
    aliases = {
        "prime-agent": "prime",
        "oh": "openhands",
        "open-hands": "openhands",
        "oc": "openclaw",
        "open-claw": "openclaw",
    }
    value = aliases.get(value, value)
    if value not in _FACTORIES:
        raise UnknownBrain(
            f"unknown brain {raw!r}. Choose one of: {', '.join(KNOWN_BRAINS)}"
        )
    return value


def get_brain(brain_id: str | None = None, cfg: Config | None = None) -> Brain:
    cfg = cfg or load_config()
    resolved = normalize_id(brain_id)
    return _FACTORIES[resolved](cfg)


def list_brains(cfg: Config | None = None) -> list[Brain]:
    cfg = cfg or load_config()
    return [_FACTORIES[name](cfg) for name in KNOWN_BRAINS]


def selected_source(cfg: Config | None = None) -> tuple[str, str]:
    """Return (brain_id, source) where source is env | file | default."""
    cfg = cfg or load_config()
    if cfg.brain_env:
        return normalize_id(cfg.brain_env), "env"
    path = selected_path()
    if path.is_file():
        raw = path.read_text(encoding="utf-8").strip().splitlines()
        if raw:
            return normalize_id(raw[0]), "file"
    return DEFAULT_BRAIN, "default"


def selected_id(cfg: Config | None = None) -> str:
    return selected_source(cfg)[0]


def selected(cfg: Config | None = None) -> Brain:
    cfg = cfg or load_config()
    return get_brain(selected_id(cfg), cfg)


def select(brain_id: str, cfg: Config | None = None) -> str:
    cfg = cfg or load_config()
    resolved = normalize_id(brain_id)
    home = brains_home()
    home.mkdir(parents=True, exist_ok=True)
    path = selected_path()
    path.write_text(resolved + "\n", encoding="utf-8")
    return resolved
