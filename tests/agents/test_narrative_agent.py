from narrative_llm_agent.agents.narrative import (
    NarrativeAgent,
    NarrativeUtil
)
from tests.test_data.test_data import load_test_data_json
from pathlib import Path
from narrative_llm_agent.config import get_config

token = "not_a_token"

def test_init(mock_llm):
    na = NarrativeAgent(token, mock_llm)
    assert na.role == "Narrative Manager"

def test_get_narrative(mock_llm, mocker, test_narrative_object):
    wsid = 123
    mock = mocker.patch.object(NarrativeUtil, "get_narrative_from_wsid", return_value=test_narrative_object)
    na = NarrativeAgent(token, mock_llm)
    narr_str = na._get_narrative(wsid)
    assert narr_str == str(test_narrative_object)
    mock.assert_called_once_with(wsid)

def test_add_markdown_cell(mock_llm, mocker, test_narrative_object):
    wsid = 123
    md_test = "# Foo\n ## Bar"
    get_mock = mocker.patch.object(NarrativeUtil, "get_narrative_from_wsid", return_value=test_narrative_object)
    save_mock = mocker.patch.object(NarrativeUtil, "save_narrative", return_value=[])
    num_cells = len(test_narrative_object.cells)
    na = NarrativeAgent(token, mock_llm)
    resp = na._add_markdown_cell(wsid, md_test)
    assert resp == "success"
    get_mock.assert_called_once_with(wsid)
    save_mock.assert_called_once_with(test_narrative_object, wsid)
    assert len(test_narrative_object.cells) == num_cells + 1
    assert test_narrative_object.cells[-1].source == md_test

def test_add_app_cell(mock_llm, mocker, mock_kbase_jsonrpc_1_call, test_narrative_object, app_spec):
    wsid = 123
    job_id = "this_is_a_job_id_to_test"
    get_mock = mocker.patch.object(NarrativeUtil, "get_narrative_from_wsid", return_value=test_narrative_object)
    save_mock = mocker.patch.object(NarrativeUtil, "save_narrative", return_value=[])
    na = NarrativeAgent(token, mock_llm)
    state_dict = load_test_data_json(Path("app_spec_data") / "app_spec_job_state.json")
    # Digging into too many details here, but good enough.
    config = get_config()
    mock_kbase_jsonrpc_1_call(config.ee_endpoint, state_dict)
    mock_kbase_jsonrpc_1_call(config.nms_endpoint, [app_spec])
    num_cells = len(test_narrative_object.cells)
    resp = na._add_app_cell(wsid, job_id)
    assert resp == "success"
    get_mock.assert_called_once_with(wsid)
    save_mock.assert_called_once_with(test_narrative_object, wsid)
    assert len(test_narrative_object.cells) == num_cells + 1
    assert test_narrative_object.cells[-1].cell_type == "code"
