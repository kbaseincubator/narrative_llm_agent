from langchain_core.language_models.llms import LLM
from narrative_llm_agent.agents.kbase_agent import KBaseAgent
import pytest

class MockLLM(LLM):
    def _call():
        pass

    def _llm_type():
        pass

@pytest.fixture
def mock_llm():
    return MockLLM()

def test_kbase_agent(mock_llm):
    fake_token = "foo"
    agent = KBaseAgent(fake_token, mock_llm)

    assert isinstance(agent._llm, LLM)
    assert agent._token == fake_token
    assert agent._service_endpoint == "https://ci.kbase.us/services/"
