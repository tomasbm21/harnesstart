"""Four-role coding crew. Separate calls, cheap or local model, no secret traces."""

from .loop import run_crew
from .model import resolve_model

__all__ = ["resolve_model", "run_crew"]
