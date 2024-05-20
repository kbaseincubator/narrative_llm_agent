from narrative_llm_agent.agents.narrative import (
    NarrativeAgent,
    NarrativeUtil
)
from narrative_llm_agent.kbase.objects.narrative import Narrative
import pytest
from tests.test_data.test_data import get_test_narrative, load_test_data_json
from pathlib import Path

token = "not_a_token"

@pytest.fixture
def test_narrative():
    return Narrative(get_test_narrative(as_dict=True))

def test_init(mock_llm):
    na = NarrativeAgent(token, mock_llm)
    assert na.role == "Narrative Manager"

def test_get_narrative(mock_llm, mocker, test_narrative):
    wsid = 123
    mock = mocker.patch.object(NarrativeUtil, "get_narrative_from_wsid", return_value=test_narrative)
    na = NarrativeAgent(token, mock_llm)
    narr_str = na._get_narrative(wsid)
    assert narr_str == str(test_narrative)
    mock.assert_called_once_with(wsid)

def test_add_markdown_cell(mock_llm, mocker, test_narrative):
    wsid = 123
    md_test = "# Foo\n ## Bar"
    get_mock = mocker.patch.object(NarrativeUtil, "get_narrative_from_wsid", return_value=test_narrative)
    save_mock = mocker.patch.object(NarrativeUtil, "save_narrative", return_value=[])
    num_cells = len(test_narrative.cells)
    na = NarrativeAgent(token, mock_llm)
    resp = na._add_markdown_cell(wsid, md_test)
    assert resp == "success"
    get_mock.assert_called_once_with(wsid)
    save_mock.assert_called_once_with(test_narrative, wsid)
    assert len(test_narrative.cells) == num_cells + 1
    assert test_narrative.cells[-1].source == md_test

def test_add_app_cell(mock_llm, mocker, mock_kbase_jsonrpc_1_call, test_narrative, app_spec):
    wsid = 123
    job_id = "this_is_a_job_id_to_test"
    get_mock = mocker.patch.object(NarrativeUtil, "get_narrative_from_wsid", return_value=test_narrative)
    save_mock = mocker.patch.object(NarrativeUtil, "save_narrative", return_value=[])
    na = NarrativeAgent(token, mock_llm)
    state_dict = load_test_data_json(Path("app_spec_data") / "app_spec_job_state.json")
    # Digging into too many details here, but good enough.
    mock_kbase_jsonrpc_1_call(na.ee_endpoint, state_dict)
    mock_kbase_jsonrpc_1_call(na.nms_endpoint, [app_spec])
    num_cells = len(test_narrative.cells)
    resp = na._add_app_cell(wsid, job_id)
    assert resp == "success"
    get_mock.assert_called_once_with(wsid)
    save_mock.assert_called_once_with(test_narrative, wsid)
    assert len(test_narrative.cells) == num_cells + 1
    assert test_narrative.cells[-1].cell_type == "code"
