import json

from narrative_llm_agent.agents.workspace import Workspace, WorkspaceAgent, WorkspaceUtil

token = "not_a_token"


def test_init(mock_llm):
    wa = WorkspaceAgent(token, mock_llm)
    assert wa.role == "Workspace Manager"


def test_list_objects_tool(mock_llm, mocker):
    ws_id = 12345
    obj_list = [{"first": "object"}, {"second": "object"}]
    mock = mocker.patch.object(Workspace, "list_workspace_objects", return_value=obj_list)
    wa = WorkspaceAgent(token, mock_llm)
    assert wa._list_objects(ws_id) == json.dumps(obj_list)
    mock.assert_called_once_with(ws_id)


def test_get_object_tool(mock_llm, mocker):
    upa = "1/2/3"
    my_obj = {"data": {"some": "data"}}
    mock = mocker.patch.object(Workspace, "get_objects", return_value=[my_obj])
    wa = WorkspaceAgent(token, mock_llm)
    assert wa._get_object(upa) == my_obj
    mock.assert_called_once_with([upa])


def test_get_report_tool(mock_llm, mocker):
    some_report = "this is a report"
    upa = "1/2/3"
    mock = mocker.patch.object(WorkspaceUtil, "get_report", return_value=some_report)
    wa = WorkspaceAgent(token, mock_llm)
    assert wa._get_report(upa) == some_report
    mock.assert_called_once_with(upa)
