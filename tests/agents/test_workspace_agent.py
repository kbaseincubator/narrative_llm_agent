import json
from narrative_llm_agent.agents.workspace import (
    ExecutionEngine,
    Workspace,
    WorkspaceAgent,
    WorkspaceUtil
)
from narrative_llm_agent.kbase.clients.execution_engine import JobState
import pytest

token = "not_a_token"
def test_init(mock_llm):
    wa = WorkspaceAgent(mock_llm, token=token)
    assert wa.role == "Workspace Manager"
    assert wa._token == token
    assert wa._llm == mock_llm

def test_list_objects_tool(mock_llm, mocker):
    ws_id = 12345
    obj_list = [{"first": "object"}, {"second": "object"}]
    mock = mocker.patch.object(Workspace, "list_workspace_objects", return_value=obj_list)
    wa = WorkspaceAgent(mock_llm)
    assert wa._list_objects(ws_id) == json.dumps(obj_list)
    mock.assert_called_once_with(ws_id)

def test_get_object_tool(mock_llm, mocker):
    upa = "1/2/3"
    my_obj = {"data": {"some": "data"}}
    mock = mocker.patch.object(Workspace, "get_objects", return_value=[my_obj])
    wa = WorkspaceAgent(mock_llm)
    assert wa._get_object(upa) == my_obj
    mock.assert_called_once_with([upa])

def test_get_report_tool(mock_llm, mocker):
    some_report = "this is a report"
    upa = "1/2/3"
    mock = mocker.patch.object(WorkspaceUtil, "get_report", return_value=some_report)
    wa = WorkspaceAgent(mock_llm)
    assert wa._get_report(upa) == some_report
    mock.assert_called_once_with(upa)


"""
cases to cover:
1. Bad job id
2. x job queued
3. x job running
4. x job error'd
5. x job terminated
6. x job complete, no outputs
7. x job complete, no report
8. job complete, has report - happy path?
9. job complete, report ref isn't a report
10. x job complete, no result field
"""
job_id_report_cases = [
    ("queued", None, "The job is not yet complete"),
    ("running", None, "The job is not yet complete"),
    ("error", None, "The job did not finish successfully, so there is no report to return."),
    ("terminated", None, "The job did not finish successfully, so there is no report to return."),
    ("other", None, "Unknown job status 'other'"),
    ("completed", None, "The job was completed, but no job output was found."),
    ("completed", {}, "The job output seems to be malformed, there is no 'result' field."),
    ("completed", {"result": [{"stuff": "things"}]}, "No report object was found in the job results."),
]
@pytest.mark.parametrize("status,job_output,expected", job_id_report_cases)
def test_get_report_from_job_id_no_report(status, job_output, expected, mock_job_states, mocker, mock_llm):
    job_id = "job_id_1"
    state = mock_job_states[job_id].copy()
    state["status"] = status
    state["job_output"] = job_output
    mock = mocker.patch.object(ExecutionEngine, "check_job", return_value=JobState(state))
    wa = WorkspaceAgent(mock_llm)
    assert wa._get_report_from_job_id(job_id) == expected
    mock.assert_called_once_with(job_id)

def test_get_report_from_id_ok(mock_job_states, mocker, mock_llm):
    job_id = "job_id_1"
    some_report = "this is a report"
    state = mock_job_states[job_id].copy()
    report_ref = "11/22/33"
    state["job_output"] = { "result": [{ "report_ref": report_ref }] }
    ee_mock = mocker.patch.object(ExecutionEngine, "check_job", return_value=JobState(state))
    ws_mock = mocker.patch.object(WorkspaceUtil, "get_report", return_value=some_report)
    wa = WorkspaceAgent(mock_llm)
    assert wa._get_report_from_job_id(job_id) == some_report
    ee_mock.assert_called_once_with(job_id)
    ws_mock.assert_called_once_with(report_ref)

