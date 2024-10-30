from narrative_llm_agent.agents.coordinator import CoordinatorAgent
import pytest

FAKE_OPENAI_KEY = "fake_openai_api_key"
FAKE_OPENAI_KEY_ENVVAR = "not_an_openai_key_environment"
OPENAI_KEY = "OPENAI_API_KEY"


@pytest.fixture(autouse=True)
def automock_api_key(monkeypatch):
    monkeypatch.setenv(OPENAI_KEY, FAKE_OPENAI_KEY_ENVVAR)


def test_init_ok(mock_llm):
    ca = CoordinatorAgent(mock_llm)
    assert ca.role == "Project coordinator"
    assert ca.agent.tools == []
