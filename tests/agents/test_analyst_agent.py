from narrative_llm_agent.agents.analyst import AnalystAgent
import os
import pytest

token = "not_a_token"
FAKE_OPENAI_KEY = "fake_openai_api_key"
FAKE_OPENAI_KEY_ENVVAR = "not_an_openai_key_environment"
OPENAI_KEY = "OPENAI_API_KEY"

def test_init(mock_llm):
    wa = AnalystAgent(token, mock_llm, openai_api_key=FAKE_OPENAI_KEY)
    assert wa.role == "Computational Biologist and Geneticist"
    assert wa._token == token
    assert wa._openai_key == FAKE_OPENAI_KEY

def test_init_with_env_var(mock_llm, monkeypatch):
    monkeypatch.setenv(OPENAI_KEY, FAKE_OPENAI_KEY_ENVVAR)
    wa = AnalystAgent(token, mock_llm)
    assert wa.role == "Computational Biologist and Geneticist"
    assert wa._token == token

def test_init_fail_without_envvar(mock_llm, monkeypatch):
    if OPENAI_KEY in os.environ:
        monkeypatch.delenv(OPENAI_KEY)
    with pytest.raises(KeyError):
        AnalystAgent(token, mock_llm)
