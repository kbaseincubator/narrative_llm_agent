from narrative_llm_agent.agents.job import JobAgent
from tests.conftest import MockLLM


def test_init(mock_llm: MockLLM):
    ja = JobAgent(mock_llm)
    assert ja.role == "Job and App Manager"
