from langchain_core.language_models.llms import LLM
from narrative_llm_agent.agents.kbase_agent import KBaseAgent


def test_kbase_agent(mock_llm):
    agent = KBaseAgent(mock_llm)

    assert isinstance(agent._llm, LLM)
    assert agent._token is None


def test_kbase_agent_with_token(mock_llm):
    fake_token = "foo"
    agent = KBaseAgent(mock_llm, fake_token)
    assert isinstance(agent._llm, LLM)
    assert agent._token == fake_token
