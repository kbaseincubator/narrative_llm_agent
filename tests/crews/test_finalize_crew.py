import pytest
from narrative_llm_agent.crews.finalize_crew import FinalizeCrew
from crewai import Task

token = "not_a_token"
FAKE_OPENAI_KEY = "fake_openai_api_key"
FAKE_OPENAI_KEY_ENVVAR = "not_an_openai_key_environment"
OPENAI_KEY = "OPENAI_API_KEY"
FAKE_CBORG_KEY = "fake_cborg_api_key"
FAKE_CBORG_KEY_ENVVAR = "not_a_cborg_key_environment"
CBORG_KEY = "CBORG_API_KEY"
FAKE_TOOLS_MODEL = "fake_model_name"

@pytest.fixture(autouse=True)
def automock_api_key(monkeypatch):
    monkeypatch.setenv(OPENAI_KEY, FAKE_OPENAI_KEY_ENVVAR)
    monkeypatch.setenv(CBORG_KEY, FAKE_CBORG_KEY_ENVVAR)

@pytest.fixture
def final_crew(mock_llm):
    return FinalizeCrew(llm=mock_llm, token="fake_token")


def test_initialization(final_crew):
    assert final_crew._token == "fake_token"
    assert isinstance(final_crew._agents, list)
    assert all(agent is not None for agent in final_crew._agents)


def test_build_tasks_returns_list(final_crew):
    narrative_id = 123
    app_list = [{"step": 1, "app_id": "kb_prokka/run_prokka"}]
    tasks = final_crew.build_tasks(narrative_id, app_list)
    assert isinstance(tasks, list)
    assert all(isinstance(t, Task) for t in tasks)
