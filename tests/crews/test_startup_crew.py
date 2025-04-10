import pytest
from narrative_llm_agent.crews.startup_crew import StartupCrew
from narrative_llm_agent.tools.job_tools import CompletedJob
from crewai import Task

@pytest.fixture
def startup_crew(mock_llm):
    return StartupCrew(llm=mock_llm, token="fake_token")


def test_initialization(startup_crew):
    assert startup_crew._token == "fake_token"
    assert isinstance(startup_crew._agents, list)
    assert all(agent is not None for agent in startup_crew._agents)


def test_build_tasks_returns_list(startup_crew):
    tasks = startup_crew.build_tasks()
    assert isinstance(tasks, list)
    assert all(isinstance(t, Task) for t in tasks)
