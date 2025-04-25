from narrative_llm_agent.agents.narrative import NarrativeAgent
from tests.conftest import MockLLM

token = "not_a_token"


def test_init(mock_llm: MockLLM):
    na = NarrativeAgent(mock_llm, token=token)
    assert na.role == "Narrative Manager"
