"""Jev Ultrafast hook. The package lives in product/jev/ (sibling-owned).

The core imports:

    from claw_jev import (
        ClawJev, observe, check_guards, choose, run, policy_status, doctor,
    )

Observe and check_guards MUST NOT call TypeSafe. choose/run read TYPESAFE_API_KEY
from the environment — never from chat.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Protocol, runtime_checkable

from .config import Config
from .paths import product_dir


class LivePolicyNeedsKey(RuntimeError):
    """Live Jev click/type policy needs TYPESAFE_API_KEY in env, not in chat."""


class AdapterMissing(RuntimeError):
    """product/jev is not on this checkout yet."""


class PolicyUnavailable(LivePolicyNeedsKey):
    """Same condition as claw_jev.PolicyUnavailable; kept if the package is absent."""


@dataclass(frozen=True)
class AdapterConfig:
    """Secret-free view. Keys stay in os.environ."""

    repo_root: Path
    cdp_url: str
    browser_profile: Path
    display: str
    typesafe_key_present: bool
    text_model_key_present: bool
    chrome_no_sandbox: bool
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ObserveResult:
    ok: bool
    url: str
    actions: tuple[dict, ...]
    adapter: str
    used_typesafe: bool = False
    detail: str = ""
    page: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "actions", tuple(self.actions))
        if self.used_typesafe:
            raise ValueError(
                "observe() must not call TypeSafe (BRIEF R4/R8; plan: guards without a key)"
            )


@dataclass(frozen=True)
class GuardsResult:
    ok: bool
    passed: int
    total: int
    adapter: str
    used_typesafe: bool = False
    detail: str = ""

    def __post_init__(self) -> None:
        if self.used_typesafe:
            raise ValueError("check_guards() must not call TypeSafe")


@runtime_checkable
class BrowserAdapter(Protocol):
    """Implemented by ClawJevAdapter (product/jev claw_jev) or a test double."""

    name: str

    def doctor(self) -> dict: ...
    def observe(self, url: str) -> ObserveResult: ...
    def check_guards(self) -> GuardsResult: ...
    def choose(self, page: dict, goal: str, history: list | None = None) -> dict: ...
    def run_policy(self, url: str, goal: str) -> Iterator[dict]: ...
    def policy_status(self) -> dict: ...
    def close(self) -> None: ...


class MissingBrowserAdapter:
    """Stand-in when product/jev is not on this checkout."""

    name = "missing-jev"

    def __init__(self, cfg: AdapterConfig):
        self.cfg = cfg

    def doctor(self) -> dict:
        return {
            "adapter": self.name,
            "present": False,
            "typesafe_required_for_observe": False,
            "typesafe_required_for_guards": False,
            "typesafe_required_for_choose": True,
            "typesafe_required_for_run_policy": True,
            "hook": "from claw_jev import ClawJev, observe, check_guards, choose, run, policy_status, doctor",
        }

    def observe(self, url: str) -> ObserveResult:
        return ObserveResult(
            ok=False,
            url=url,
            actions=(),
            adapter=self.name,
            used_typesafe=False,
            detail="Jev adapter not installed (product/jev). Observe does not need TypeSafe.",
        )

    def check_guards(self) -> GuardsResult:
        return GuardsResult(
            ok=True,
            passed=0,
            total=0,
            adapter=self.name,
            used_typesafe=False,
            detail="Jev adapter not installed; local R6 guards still run without TypeSafe.",
        )

    def choose(self, page: dict, goal: str, history: list | None = None) -> dict:
        raise AdapterMissing(_missing_msg())

    def run_policy(self, url: str, goal: str) -> Iterator[dict]:
        raise AdapterMissing(_missing_msg())
        yield  # pragma: no cover — makes this a generator

    def policy_status(self) -> dict:
        return {
            "choose": False,
            "type_text": False,
            "observe_needs_key": False,
            "guards_need_key": False,
            "adapter": self.name,
        }

    def close(self) -> None:
        return None


class ClawJevAdapter:
    """Wraps product/jev's claw_jev package. Does not own that tree."""

    name = "claw-jev"

    def __init__(self, cfg: AdapterConfig, module: Any):
        self.cfg = cfg
        self._mod = module
        self._session: Any = None

    def doctor(self) -> dict:
        report = dict(self._mod.doctor())
        report["adapter"] = self.name
        report["present"] = True
        report["typesafe_required_for_observe"] = False
        report["typesafe_required_for_guards"] = False
        report["typesafe_required_for_choose"] = True
        report["typesafe_required_for_run_policy"] = True
        report["policy"] = self._mod.policy_status()
        return report

    def observe(self, url: str) -> ObserveResult:
        try:
            session = self._mod.ClawJev()
            self._session = session
            page = session.observe(url, screenshot=False)
        except Exception as exc:  # Chrome/CDP/deps — still must not demand TypeSafe
            if _is_policy_unavailable(exc):
                raise PolicyUnavailable(str(exc)) from exc
            return ObserveResult(
                ok=False,
                url=url,
                actions=(),
                adapter=self.name,
                used_typesafe=False,
                detail=f"observe failed without TypeSafe: {type(exc).__name__}",
            )
        actions = tuple(page.get("actions") or ())
        title = page.get("title") or ""
        return ObserveResult(
            ok=True,
            url=str(page.get("url") or url),
            actions=actions,
            adapter=self.name,
            used_typesafe=False,
            detail=f"{len(actions)} actions; title={title}",
            page={k: v for k, v in page.items() if k != "screenshot"},
        )

    def check_guards(self) -> GuardsResult:
        try:
            report = self._mod.check_guards()
        except Exception as exc:
            if _is_policy_unavailable(exc):
                raise PolicyUnavailable(str(exc)) from exc
            return GuardsResult(
                ok=False,
                passed=0,
                total=0,
                adapter=self.name,
                used_typesafe=False,
                detail=f"check_guards failed without TypeSafe: {type(exc).__name__}",
            )
        if report.get("typesafe_required"):
            raise ValueError("check_guards() must not call TypeSafe")
        passed = int(report.get("passed") or 0)
        checks = report.get("checks") or []
        total = len(checks) if checks else passed
        return GuardsResult(
            ok=bool(report.get("ok", passed > 0)),
            passed=passed,
            total=total,
            adapter=self.name,
            used_typesafe=False,
            detail=f"{passed}/{total} browser guard checks; no model calls",
        )

    def choose(self, page: dict, goal: str, history: list | None = None) -> dict:
        try:
            return self._mod.choose(page, goal, history)
        except Exception as exc:
            if _is_policy_unavailable(exc):
                raise PolicyUnavailable(str(exc)) from exc
            raise

    def run_policy(self, url: str, goal: str) -> Iterator[dict]:
        try:
            session = self._mod.ClawJev()
            self._session = session
            yield from session.run(url, goal)
        except Exception as exc:
            if _is_policy_unavailable(exc):
                raise PolicyUnavailable(str(exc)) from exc
            raise

    def policy_status(self) -> dict:
        status = dict(self._mod.policy_status())
        status["adapter"] = self.name
        return status

    def close(self) -> None:
        session = self._session
        self._session = None
        if session is not None and hasattr(session, "close"):
            session.close()


def adapter_config(cfg: Config) -> AdapterConfig:
    return AdapterConfig(
        repo_root=cfg.repo_root,
        cdp_url=cfg.cdp_url,
        browser_profile=cfg.browser_profile,
        display=cfg.display,
        typesafe_key_present=cfg.typesafe_key,
        text_model_key_present=cfg.text_model_key,
        chrome_no_sandbox=cfg.chrome_no_sandbox,
    )


def load_browser_adapter(cfg: Config) -> BrowserAdapter:
    hook_cfg = adapter_config(cfg)
    if cfg.browser_adapter_spec:
        return _load_spec(cfg.browser_adapter_spec, hook_cfg)
    module = import_claw_jev(cfg.repo_root)
    if module is not None:
        return ClawJevAdapter(hook_cfg, module)
    jev_dir = product_dir(cfg.repo_root) / "jev"
    for filename in ("adapter.py",):
        path = jev_dir / filename
        if path.is_file():
            loaded = _load_file(path, hook_cfg)
            if loaded is not None:
                return loaded
    return MissingBrowserAdapter(hook_cfg)


def import_claw_jev(repo_root: Path) -> Any | None:
    """Load claw_jev from product/jev without taking over that tree.

    Uses the public surface:
    ClawJev, observe, check_guards, choose, run, policy_status, doctor
    """
    jev_dir = product_dir(repo_root) / "jev"
    pkg = jev_dir / "claw_jev"
    if not pkg.is_dir():
        return None
    paths = [str(jev_dir)]
    site = _jev_site_packages(jev_dir)
    if site is not None:
        paths.insert(0, str(site))
    for path in reversed(paths):
        if path not in sys.path:
            sys.path.insert(0, path)
    existing = sys.modules.get("claw_jev")
    if existing is not None:
        origin = getattr(existing, "__file__", "") or ""
        if origin and not origin.startswith(str(pkg)):
            _drop_claw_jev_modules()
    try:
        module = importlib.import_module("claw_jev")
    except Exception:
        return None
    required = (
        "ClawJev",
        "observe",
        "check_guards",
        "choose",
        "run",
        "policy_status",
        "doctor",
    )
    if not all(hasattr(module, name) for name in required):
        return None
    return module


def _jev_site_packages(jev_dir: Path) -> Path | None:
    """Use product/jev/.venv if the sibling already ran uv sync (not owned here)."""
    lib = jev_dir / ".venv" / "lib"
    if not lib.is_dir():
        return None
    matches = sorted(lib.glob("python*/site-packages"))
    return matches[-1] if matches else None


def require_live_policy_key(cfg: Config) -> None:
    if not cfg.typesafe_key:
        raise PolicyUnavailable(
            "Live Jev choose()/run() need TYPESAFE_API_KEY in claw.env or the "
            "process environment. Observe and guards do not. Do not paste the key in chat."
        )


def _missing_msg() -> str:
    return (
        "Live browser policy needs product/jev (claw_jev). "
        "That directory is owned by PR https://github.com/tomasbm21/harnesstart/pull/1"
    )


def _is_policy_unavailable(exc: BaseException) -> bool:
    if isinstance(exc, LivePolicyNeedsKey):
        return True
    return type(exc).__name__ in {"PolicyUnavailable", "LivePolicyNeedsKey"}


def _drop_claw_jev_modules() -> None:
    for name in list(sys.modules):
        if name == "claw_jev" or name.startswith("claw_jev."):
            sys.modules.pop(name, None)


def _load_spec(spec: str, hook_cfg: AdapterConfig) -> BrowserAdapter:
    if ":" in spec:
        mod_name, _, attr = spec.partition(":")
    else:
        mod_name, attr = spec, ""
    module = importlib.import_module(mod_name)
    obj = getattr(module, attr) if attr else module
    return _coerce(obj, hook_cfg)


def _load_file(path: Path, hook_cfg: AdapterConfig) -> BrowserAdapter | None:
    name = f"norfront_claw_jev_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    obj = None
    for attr in ("create_adapter", "ADAPTER", "adapter"):
        if hasattr(module, attr):
            obj = getattr(module, attr)
            break
    if obj is None:
        return None
    return _coerce(obj, hook_cfg)


def _coerce(obj: object, hook_cfg: AdapterConfig) -> BrowserAdapter:
    if callable(obj) and not isinstance(obj, type):
        return obj(hook_cfg)  # type: ignore[operator]
    if isinstance(obj, type):
        try:
            return obj(hook_cfg)  # type: ignore[misc]
        except TypeError:
            return obj()  # type: ignore[misc]
    return obj  # type: ignore[return-value]


def jev_skill_dir(root: Path) -> Path | None:
    """Optional Prime Agent skill shipped by the Jev sibling."""
    for rel in ("product/jev/prime-skill", "product/jev/skill"):
        path = root / rel
        if path.is_dir() and any(path.iterdir()):
            return path
    return None


def typesafe_in_environ() -> bool:
    return bool(os.environ.get("TYPESAFE_API_KEY", "").strip())


def live_browser_opt_in() -> bool:
    """True only when CLAW_BROWSER_LIVE=1.

    Default CI and ``./product/claw test`` leave this unset. Observe and
    guards do not consult it. Live choose/browse stays a separate opt-in
    path so a missing TypeSafe key cannot hang a run (non-TTY, no prompt).
    """
    return os.environ.get("CLAW_BROWSER_LIVE", "").strip() == "1"
