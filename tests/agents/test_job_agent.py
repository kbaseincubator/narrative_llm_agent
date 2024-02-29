from narrative_llm_agent.agents.job import JobAgent

token = "not_a_token"
def test_init(mock_llm):
    wa = JobAgent(token, mock_llm)
    assert wa.role == "Job Manager"
