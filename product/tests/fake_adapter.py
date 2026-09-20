"""Minimal BrowserAdapter used by unit tests. No TypeSafe, no Chrome."""

from __future__ import annotations

from norfront_claw.browser import (
    AdapterConfig,
    GuardsResult,
    PolicyUnavailable,
    ObserveResult,
)


class FakeAdapter:
    name = "fake-jev"

    def __init__(self, cfg: AdapterConfig):
        self.cfg = cfg

    def doctor(self) -> dict:
        return {
            "adapter": self.name,
            "present": True,
            "typesafe_required_for_observe": False,
            "typesafe_required_for_guards": False,
            "typesafe_required_for_run_policy": True,
            "typesafe_key_present": self.cfg.typesafe_key_present,
        }

    def observe(self, url: str) -> ObserveResult:
        return ObserveResult(
            ok=True,
            url=url,
            actions=({"id": 1, "kind": "click", "label": "Example"},),
            adapter=self.name,
            used_typesafe=False,
            detail="fake observe; no TypeSafe",
        )

    def check_guards(self) -> GuardsResult:
        return GuardsResult(
            ok=True,
            passed=3,
            total=3,
            adapter=self.name,
            used_typesafe=False,
            detail="fake guards; no TypeSafe",
        )

    def choose(self, page: dict, goal: str, history: list | None = None) -> dict:
        if not self.cfg.typesafe_key_present:
            raise PolicyUnavailable(
                "Live Jev choose()/run() need TYPESAFE_API_KEY in the environment "
                "(not chat). Observe and guards do not."
            )
        return {"operation": "WAIT", "goal": goal, "adapter": self.name}

    def run_policy(self, url: str, goal: str):
        if not self.cfg.typesafe_key_present:
            raise PolicyUnavailable(
                "Live Jev choose()/run() need TYPESAFE_API_KEY in the environment "
                "(not chat). Observe and guards do not."
            )
        yield {"url": url, "goal": goal, "status": "stub-live", "adapter": self.name}

    def policy_status(self) -> dict:
        return {
            "choose": self.cfg.typesafe_key_present,
            "type_text": self.cfg.text_model_key_present,
            "observe_needs_key": False,
            "guards_need_key": False,
            "adapter": self.name,
        }

    def close(self) -> None:
        return None


def create_adapter(cfg: AdapterConfig) -> FakeAdapter:
    return FakeAdapter(cfg)
