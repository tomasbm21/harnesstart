"""Observe and run through Jev without attaching to the human Chrome profile."""

from __future__ import annotations

from collections.abc import Iterator

from claw_jev.chrome import ChromeSession, global_session
from claw_jev.policy import PolicyUnavailable, choose as policy_choose, require_choose


def _public_page(page: dict, *, include_screenshot: bool) -> dict:
    if include_screenshot:
        return page
    return {key: value for key, value in page.items() if key != "screenshot"}


class ClawJev:
    """Core-facing session: start dedicated Chrome, observe, optionally choose/run."""

    def __init__(self, **chrome_kwargs):
        self.chrome = global_session(**chrome_kwargs) if not chrome_kwargs else ChromeSession(**chrome_kwargs)
        self._browser = None

    def start(self) -> dict:
        return self.chrome.ensure()

    def _open(self, url: str):
        self.start()
        from jev_ultrafast.browser import Browser

        if self._browser is not None:
            self._browser.close()
        self._browser = Browser(url)
        return self._browser

    def observe(self, url: str, *, screenshot: bool = False) -> dict:
        """Navigate and snapshot. No TypeSafe call."""
        browser = self._open(url)
        return _public_page(browser.observe(screenshot=screenshot), include_screenshot=screenshot)

    def choose(self, page: dict, goal: str, history: list | None = None) -> dict:
        return policy_choose(page, goal, history)

    def run(self, url: str, goal: str, *, record_dir=None, screenshots: bool = False) -> Iterator[dict]:
        """Full Jev loop. Requires TYPESAFE_API_KEY (TYPE_TEXT also needs TEXT_MODEL_API_KEY)."""
        require_choose()
        self.start()
        from jev_ultrafast import Agent

        agent = Agent(url, goal, record_dir=record_dir, screenshots=screenshots)
        try:
            yield from agent.run()
        finally:
            agent.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_args):
        self.close()


def observe(url: str, *, screenshot: bool = False) -> dict:
    with ClawJev() as session:
        return session.observe(url, screenshot=screenshot)


def run(url: str, goal: str, **kwargs) -> list[dict]:
    require_choose()
    with ClawJev() as session:
        return list(session.run(url, goal, **kwargs))


# Re-export so callers can catch the same class from session or policy.
PolicyUnavailable = PolicyUnavailable
