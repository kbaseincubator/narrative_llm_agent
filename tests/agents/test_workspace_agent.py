from narrative_llm_agent.agents.workspace import WorkspaceAgent

token = "not_a_token"


def test_init(mock_llm):
    wa = WorkspaceAgent(mock_llm, token=token)
    assert wa.role == "Workspace Manager"
    assert wa._token == token
    assert wa._llm == mock_llm
