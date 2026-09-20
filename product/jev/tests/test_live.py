import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.live


def _chrome_ok() -> bool:
    try:
        from claw_jev.chrome import chrome_binary

        chrome_binary()
        return True
    except FileNotFoundError:
        return False


skip_no_chrome = pytest.mark.skipif(not _chrome_ok(), reason="Chrome is not installed")


@skip_no_chrome
def test_observe_example_com_without_typesafe_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("TEXT_MODEL_API_KEY", raising=False)
    from claw_jev import observe, policy_status

    assert policy_status()["choose"] is False
    page = observe("https://example.com")
    assert "example.com" in page["url"]
    assert page.get("title")
    assert isinstance(page.get("actions"), list)
    assert page["actions"], "expected indexed controls (e.g. Learn more, wait)"
    assert "screenshot" not in page
    labels = [a.get("label", "") for a in page["actions"]]
    kinds = {a.get("kind") for a in page["actions"]}
    assert "wait" in kinds or any("more" in label.lower() for label in labels)


@skip_no_chrome
def test_guards_without_typesafe_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    from claw_jev import check_guards

    report = check_guards()
    assert report["ok"] is True
    assert report["passed"] == 21
    assert report["model_calls"] == 0
    assert report["typesafe_required"] is False


@skip_no_chrome
def test_doctor_after_dedicated_chrome_start(monkeypatch, tmp_path):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    from claw_jev.chrome import ChromeSession, assert_dedicated_profile, doctor

    info = ChromeSession().ensure()
    assert "Chrome" in (info.get("Browser") or "")
    report = doctor()
    assert report["cdp_ok"] is True
    assert report["user_data_dir_ok"] is True
    assert report["no_sandbox"] is True or os.environ.get("CLAW_JEV_SANDBOX") == "1"
    assert_dedicated_profile(Path(report["user_data_dir"]))
    assert Path.home() / ".config/google-chrome" != Path(report["user_data_dir"])
    assert report["policy"]["choose"] is False
    assert report["policy"]["observe_needs_key"] is False


@skip_no_chrome
def test_run_without_key_exits_unavailable(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    from claw_jev import PolicyUnavailable, run

    with pytest.raises(PolicyUnavailable):
        run("https://example.com", "Stop when the heading is visible.")
