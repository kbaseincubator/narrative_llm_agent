from narrative_llm_agent.agents.workspace import WorkspaceAgent

token = "not_a_token"
def test_init(mock_llm):
    wa = WorkspaceAgent(token, mock_llm)
    assert wa.role == "Workspace Manager"

def test_list_objects_tool(mock_llm):
    wa = WorkspaceAgent(token, mock_llm)

def test_get_object_tool(mock_llm):
    wa = WorkspaceAgent(token, mock_llm)

def test_get_report_tool(mock_llm):
    wa = WorkspaceAgent(token, mock_llm)
