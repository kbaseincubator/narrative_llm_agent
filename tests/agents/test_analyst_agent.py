from narrative_llm_agent.agents.analyst import AnalystAgent

token = "not_a_token"
def test_init(mock_llm):
    wa = AnalystAgent(token, mock_llm)
    assert wa.role == "Computational Biologist and Geneticist"
