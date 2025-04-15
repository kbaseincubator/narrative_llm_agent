from narrative_llm_agent.agents.metadata import MetadataAgent

token = "NotAToken"

def test_init(mock_llm):
    ma = MetadataAgent(mock_llm, token=token)
    assert ma.role == "Human Interaction Manager"
