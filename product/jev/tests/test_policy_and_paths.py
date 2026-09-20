import json
import os
from pathlib import Path

import pytest

from claw_jev.chrome import HumanProfileError, assert_dedicated_profile, default_user_data_dir
from claw_jev.policy import PolicyUnavailable, choose, policy_status


def test_rejects_linux_human_profile():
    with pytest.raises(HumanProfileError, match="human/default profile"):
        assert_dedicated_profile(Path.home() / ".config/google-chrome")


def test_rejects_nested_human_profile():
    with pytest.raises(HumanProfileError):
        assert_dedicated_profile(Path.home() / ".config/google-chrome" / "Default")


def test_accepts_dedicated_dir(tmp_path):
    path = tmp_path / "jev-chrome"
    path.mkdir()
    assert assert_dedicated_profile(path) == path.resolve()


def test_default_dir_is_not_human(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAW_JEV_USER_DATA_DIR", str(tmp_path / "dedicated"))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    resolved = assert_dedicated_profile(default_user_data_dir())
    assert resolved == (tmp_path / "dedicated").resolve()
    assert ".config/google-chrome" not in str(resolved)


def test_choose_blocked_without_typesafe_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("TEXT_MODEL_API_KEY", raising=False)
    with pytest.raises(PolicyUnavailable, match="TYPESAFE_API_KEY"):
        choose({"url": "https://example.com", "actions": []}, "look around")


def test_policy_status_hides_key_material(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "should-never-appear-in-status")
    monkeypatch.setenv("TEXT_MODEL_API_KEY", "also-never-appear")
    status = policy_status()
    dumped = json.dumps(status)
    assert "should-never-appear-in-status" not in dumped
    assert "also-never-appear" not in dumped
    assert status["choose"] is True
    assert status["type_text"] is True
    assert status["observe_needs_key"] is False
    assert status["guards_need_key"] is False


def test_policy_status_unset(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("TEXT_MODEL_API_KEY", raising=False)
    status = policy_status()
    assert status == {
        "choose": False,
        "type_text": False,
        "observe_needs_key": False,
        "guards_need_key": False,
    }


def test_chrome_child_env_strips_secrets(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "secret-value")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "other-secret")
    monkeypatch.setenv("GH_TOKEN", "token-secret")
    monkeypatch.setenv("DISPLAY", ":1")
    from claw_jev.chrome import _chrome_child_env

    env = _chrome_child_env()
    assert "TYPESAFE_API_KEY" not in env
    assert "DEEPSEEK_API_KEY" not in env
    assert "GH_TOKEN" not in env
    assert "secret-value" not in env.values()
    assert env.get("DISPLAY") == ":1"


def test_load_env_file_setdefault_does_not_override(monkeypatch, tmp_path):
    monkeypatch.setenv("TYPESAFE_API_KEY", "keep-existing")
    monkeypatch.delenv("TEXT_MODEL_API_KEY", raising=False)
    path = tmp_path / "keys.env"
    path.write_text("TYPESAFE_API_KEY=from-file\nTEXT_MODEL_API_KEY=file-text\n")
    from claw_jev.cli import _load_env_file

    _load_env_file(path)
    assert os.environ["TYPESAFE_API_KEY"] == "keep-existing"
    assert os.environ["TEXT_MODEL_API_KEY"] == "file-text"
    monkeypatch.delenv("TEXT_MODEL_API_KEY", raising=False)
