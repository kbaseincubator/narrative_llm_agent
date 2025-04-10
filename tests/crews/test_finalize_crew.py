import pytest
from narrative_llm_agent.crews.finalize_crew import FinalizeCrew
from narrative_llm_agent.tools.job_tools import CompletedJob
from crewai import Task

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
