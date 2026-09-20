"""Optional Linux-cloud brains for Norfront Claw.

Prime Agent remains the **default** brain (owned by `product/claw`). This
package wires OpenHands, OpenClaw, and Goose as selectable backends and
exposes a JSON doctor the claw CLI can call later:

    from claw_brains import doctor, selected, select, list_brains

or:

    ./product/brains/claw-brains doctor --json
"""

__version__ = "0.1.0"

from .config import Config, load_config
from .doctor import doctor_payload
from .registry import list_brains, select, selected, selected_id

__all__ = [
    "Config",
    "doctor",
    "list_brains",
    "load_config",
    "select",
    "selected",
    "selected_id",
    "__version__",
]


def doctor(*, brain: str | None = None, cfg: Config | None = None) -> dict:
    """JSON the claw CLI can ingest later (same idea as claw-vm doctor --json)."""
    return doctor_payload(cfg or load_config(), brain=brain)
