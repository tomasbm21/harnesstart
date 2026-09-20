"""Named Prime Agent sessions. Not a Hermes kanban (that stays stubbed)."""

from __future__ import annotations

from dataclasses import dataclass

from .brain import PrimeBrain


@dataclass(frozen=True)
class SwarmView:
    backend: str
    detail: str
    stub: str


def snapshot(brain: PrimeBrain) -> SwarmView:
    if brain.which() is None:
        return SwarmView(
            backend="prime-agent",
            detail="prime-agent not installed",
            stub="Hermes-style boards/cards/GATE-A/B are not this product. Use prime-agent list/send/attach.",
        )
    listing = brain.list_agents()
    return SwarmView(
        backend="prime-agent",
        detail=listing or "No agents (daemon starts on the first claw run / prime-agent session).",
        stub="Hermes-style boards/cards/GATE-A/B are not this product. Use prime-agent list/send/attach.",
    )
