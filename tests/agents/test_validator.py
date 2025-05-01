from narrative_llm_agent.agents.validator import WorkflowValidatorAgent
import pytest

FAKE_OPENAI_KEY = "fake_openai_api_key"
FAKE_OPENAI_KEY_ENVVAR = "not_an_openai_key_environment"
OPENAI_KEY = "OPENAI_API_KEY"


@pytest.fixture(autouse=True)
def automock_api_key(monkeypatch):
    monkeypatch.setenv(OPENAI_KEY, FAKE_OPENAI_KEY_ENVVAR)


def test_init_ok(mock_llm):
    wa = WorkflowValidatorAgent(mock_llm)
    assert wa.role == "You are a workflow validator, responsible for analyzing app run results and determining next steps."
    assert wa.agent.tools == []
