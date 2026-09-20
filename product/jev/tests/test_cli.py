from claw_jev.cli import main


def test_policy_cli_json_has_no_secret(capsys, monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "leaked-if-printed")
    assert main(["policy"]) == 0
    out = capsys.readouterr().out
    assert "leaked-if-printed" not in out
    assert '"choose": true' in out
