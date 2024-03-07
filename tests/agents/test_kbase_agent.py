from langchain_core.language_models.llms import LLM
from narrative_llm_agent.agents.kbase_agent import KBaseAgent

def test_kbase_agent(mock_llm):
    fake_token = "foo"
    agent = KBaseAgent(fake_token, mock_llm)

    assert isinstance(agent._llm, LLM)
    assert agent._token == fake_token
    assert agent._service_endpoint == "https://ci.kbase.us/services/"
