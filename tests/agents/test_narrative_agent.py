from narrative_llm_agent.agents.narrative import NarrativeAgent

token = "not_a_token"

def test_init(mock_llm):
    na = NarrativeAgent(token, mock_llm)
    assert na.role == "Narrative Manager"
