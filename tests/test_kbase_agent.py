from narrative_llm_agent.agents.kbase_agent import KBaseAgent

def test_kbase_agent():
    agent = KBaseAgent("foo", None)
    assert agent._token == "foo"
    print("like totally passed.")
