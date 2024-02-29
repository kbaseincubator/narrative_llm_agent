from narrative_llm_agent.agents.workspace import WorkspaceAgent

token = "not_a_token"
def test_init(mock_llm):
    wa = WorkspaceAgent(token, mock_llm)
    assert wa.role == "Workspace Manager"
