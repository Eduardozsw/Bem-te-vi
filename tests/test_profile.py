from unittest.mock import patch, mock_open
from src.profile import load_profile


def test_load_profile_from_env_var(monkeypatch):
    monkeypatch.setenv("USER_PROFILE", "projetos:\n  MindDoc:\n    descricao: app")
    assert load_profile() == {"projetos": {"MindDoc": {"descricao": "app"}}}


def test_env_var_takes_precedence_over_file(monkeypatch):
    monkeypatch.setenv("USER_PROFILE", "from: env")
    with patch("src.profile.open", mock_open(read_data="from: file")):
        assert load_profile() == {"from": "env"}


def test_load_profile_from_file_when_no_env(monkeypatch):
    monkeypatch.delenv("USER_PROFILE", raising=False)
    with patch("src.profile.open", mock_open(read_data="investimentos:\n  cripto: BTC")):
        assert load_profile() == {"investimentos": {"cripto": "BTC"}}


def test_returns_empty_when_no_env_and_no_file(monkeypatch):
    monkeypatch.delenv("USER_PROFILE", raising=False)
    with patch("src.profile.open", side_effect=FileNotFoundError):
        assert load_profile() == {}


def test_invalid_yaml_falls_back_to_empty(monkeypatch):
    monkeypatch.setenv("USER_PROFILE", "key: [unclosed")
    assert load_profile() == {}


def test_non_dict_yaml_falls_back_to_empty(monkeypatch):
    monkeypatch.setenv("USER_PROFILE", "just a string")
    assert load_profile() == {}
