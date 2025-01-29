from typing import Callable
from pytest_mock import MockerFixture
from narrative_llm_agent.agents.narrative import NarrativeAgent, NarrativeUtil
from narrative_llm_agent.kbase.objects.app_spec import AppSpec
from narrative_llm_agent.kbase.objects.narrative import Narrative
from tests.conftest import MockLLM
from tests.test_data.test_data import load_test_data_json
from pathlib import Path
from narrative_llm_agent.config import get_config

token = "not_a_token"


def test_init(mock_llm: MockLLM):
    na = NarrativeAgent(mock_llm, token=token)
    assert na.role == "Narrative Manager"


def test_get_narrative(
    mock_llm: MockLLM, mocker: MockerFixture, test_narrative_object: Narrative
):
    wsid = 123
    mock = mocker.patch.object(
        NarrativeUtil, "get_narrative_from_wsid", return_value=test_narrative_object
    )
    na = NarrativeAgent(mock_llm, token=token)
    narr_str = na._get_narrative(wsid)
    assert narr_str == str(test_narrative_object)
    mock.assert_called_once_with(wsid)


def test_add_markdown_cell(
    mock_llm: MockLLM, mocker: MockerFixture, test_narrative_object: Narrative
):
    wsid = 123
    md_test = "# Foo\n ## Bar"
    get_mock = mocker.patch.object(
        NarrativeUtil, "get_narrative_from_wsid", return_value=test_narrative_object
    )
    save_mock = mocker.patch.object(NarrativeUtil, "save_narrative", return_value=[])
    num_cells = len(test_narrative_object.cells)
    na = NarrativeAgent(mock_llm, token=token)
    resp = na._add_markdown_cell(wsid, md_test)
    assert resp == "success"
    get_mock.assert_called_once_with(wsid)
    save_mock.assert_called_once_with(test_narrative_object, wsid)
    assert len(test_narrative_object.cells) == num_cells + 1
    assert test_narrative_object.cells[-1].source == md_test


def test_add_app_cell(
    mock_llm: MockLLM,
    mocker: MockerFixture,
    mock_kbase_jsonrpc_1_call: Callable,
    test_narrative_object: Narrative,
    app_spec: AppSpec,
):
    wsid = 123
    job_id = "this_is_a_job_id_to_test"
    get_mock = mocker.patch.object(
        NarrativeUtil, "get_narrative_from_wsid", return_value=test_narrative_object
    )
    save_mock = mocker.patch.object(NarrativeUtil, "save_narrative", return_value=[])
    na = NarrativeAgent(mock_llm, token=token)
    state_dict = load_test_data_json(Path("app_spec_data") / "app_spec_job_state.json")
    # Digging into too many details here, but good enough.
    config = get_config()
    mock_kbase_jsonrpc_1_call(config.ee_endpoint, state_dict)
    mock_kbase_jsonrpc_1_call(config.nms_endpoint, [app_spec.model_dump()])
    num_cells = len(test_narrative_object.cells)
    resp = na._add_app_cell(wsid, job_id)
    assert resp == "success"
    get_mock.assert_called_once_with(wsid)
    save_mock.assert_called_once_with(test_narrative_object, wsid)
    assert len(test_narrative_object.cells) == num_cells + 1
    assert test_narrative_object.cells[-1].cell_type == "code"
