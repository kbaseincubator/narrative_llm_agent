import json
from pathlib import Path
from typing import Any, Callable

import pytest
from pytest_mock import MockerFixture
from narrative_llm_agent.config import get_config
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine
from narrative_llm_agent.kbase.clients.narrative_method_store import (
    NarrativeMethodStore,
)
from narrative_llm_agent.kbase.clients.workspace import Workspace, WorkspaceInfo
from narrative_llm_agent.kbase.objects.app_spec import AppSpec
from narrative_llm_agent.kbase.objects.narrative import Narrative
from narrative_llm_agent.kbase.service_client import ServerError
from narrative_llm_agent.tools.narrative_tools import (
    create_app_cell,
    create_markdown_cell,
    get_all_markdown_text,
    get_narrative_from_wsid,
    get_narrative_ref_from_wsid,
    get_narrative_state,
    save_narrative,
)
from tests.test_data.test_data import get_test_narrative, load_test_data_json


class MockWorkspaceInfo(WorkspaceInfo):
    def __init__(self, ws_id, include_meta=True):
        info = [ws_id, "my_ws", "me", "123", 5, "a", "n", "n"]
        meta = {"narrative": 1, "is_temporary": 0} if include_meta else {}
        info.append(meta)
        super().__init__(info)


class MockWorkspace(Workspace):
    def __init__(
        self,
        missing_ws: bool = False,
        missing_narr_meta: bool = False,
        wrong_narr_type: bool = False,
    ) -> None:
        self.missing_ws = missing_ws
        self.missing_narr_meta = missing_narr_meta
        self.wrong_narr_type = wrong_narr_type

    def get_workspace_info(self, ws_id: int) -> WorkspaceInfo:
        if self.missing_ws:
            raise ServerError("no workspace", 500, f"no workspace with id {ws_id}")
        include_meta = False if self.missing_narr_meta else True
        return MockWorkspaceInfo(ws_id, include_meta=include_meta)

    def save_objects(self, ws_id: int, objects: list[Any]) -> list[list[Any]]:
        return [self._fake_save_narr_info(ws_id)] * len(objects)

    def get_objects(self, refs: list[str]) -> dict:
        return [self._fake_narr_obj()] * len(refs)

    def _fake_narr_obj(self):
        narr_dict = get_test_narrative(as_dict=True)
        obj_type = "KBaseNarrative.Narrative"
        if self.wrong_narr_type:
            obj_type = "NotANarrative.NotNarrative"
        return {"info": [1, "my_narrative", obj_type], "data": narr_dict}

    def _fake_save_narr_info(self, ws_id: int):
        return [
            1,
            "my_narr",
            "KBaseNarrative.Narrative-4.0",
            "2024-02-12T21:25:47+0000",
            5,
            "me",
            ws_id,
            "some_ws",
            "f420c24227bc252cbf8110cd82f769be",
            13549,
            {
                "creator": "me",
                "data_dependencies": "[]",
                "method.kb_fastqc/runFastQC/b7ea69cd0fe0f62e45a8e6ea4ddeba3cba17a8d4": "1",
                "job_info": '{"queue_time": 0, "run_time": 0, "running": 0, "completed": 0, "error": 0}',
                "format": "ipynb",
                "name": "My Fancy Narrative",
                "description": "",
                "ws_name": "some_ws",
            },
        ]


def test_get_ref_from_wsid():
    ws = MockWorkspace()
    assert get_narrative_ref_from_wsid(666, ws) == "666/1"


def test_get_ref_from_wsid_missing_ws():
    ws = MockWorkspace(missing_ws=True)
    with pytest.raises(ServerError) as exc_info:
        get_narrative_ref_from_wsid(123, ws)
    assert "no workspace with id" in str(exc_info.value)


def test_get_ref_from_wsid_no_narr():
    ws = MockWorkspace(missing_narr_meta=True)
    with pytest.raises(ValueError) as exc_info:
        get_narrative_ref_from_wsid(123, ws)
    assert "No narrative found in workspace 123" in str(exc_info.value)


def test_get_narrative_from_wsid():
    ws = MockWorkspace()
    narr = get_narrative_from_wsid(123, ws)
    assert isinstance(narr, Narrative)


def test_get_narrative_from_wsid_wrong_type():
    ws = MockWorkspace(wrong_narr_type=True)
    with pytest.raises(ValueError) as exc_info:
        get_narrative_from_wsid(123, ws)
    assert "The object with reference 123/1 is not a KBase Narrative" in str(
        exc_info.value
    )


def test_get_narrative_from_wsid_missing_ws():
    pass


def test_get_narrative_from_wsid_no_narr():
    pass


def test_save_narrative(mocker: MockerFixture):
    ws_id = 123
    mocker.patch.object(
        Workspace, "get_workspace_info", return_value=MockWorkspaceInfo(ws_id)
    )
    mocker.patch.object(Workspace, "save_objects", return_value=[["my", "info"]])
    fake_ws = Workspace("fake", "not_an_endpoint")
    narr = Narrative(get_test_narrative(as_dict=True))
    obj_info = save_narrative(narr, ws_id, fake_ws)
    # spot check since it's all fake anyway
    assert obj_info == ["my", "info"]
    fake_ws.save_objects.assert_called_once()
    args = fake_ws.save_objects.call_args.args
    assert args[0] == ws_id
    obj = args[1][0]
    assert obj["type"] == "KBaseNarrative.Narrative"
    assert obj["data"] == narr.to_dict()
    assert str(obj["objid"]) == "1"
    assert obj["provenance"] == [
        {
            "service": "narrative_llm_agent",
            "description": "Saved by a KBase Assistant",
            "service_ver": "0.0.1",
        }
    ]
    expected_keys = [
        "creator",
        "format",
        "name",
        "description",
        "data_dependencies",
        "job_info",
    ]
    for key in expected_keys:
        assert key in obj["meta"]


def test_create_markdown_cell(mocker: MockerFixture, test_narrative_object: Narrative):
    ws_id = 123
    conversation = "This is very important."
    narr = test_narrative_object
    get_mock = mocker.patch(
        "narrative_llm_agent.tools.narrative_tools.get_narrative_from_wsid",
        return_value=narr,
    )
    save_mock = mocker.patch(
        "narrative_llm_agent.tools.narrative_tools.save_narrative", return_value=[]
    )
    num_cells = len(narr.cells)
    mock_ws = MockWorkspace()
    resp = create_markdown_cell(ws_id, conversation, mock_ws)
    assert resp == "Conversation successfully stored."
    get_mock.assert_called_once_with(ws_id, mock_ws)
    save_mock.assert_called_once_with(narr, ws_id, mock_ws)
    assert len(narr.cells) == num_cells + 1
    assert narr.cells[-1].source == conversation


def test_create_app_cell(
    mocker: MockerFixture,
    mock_kbase_jsonrpc_1_call: Callable,
    test_narrative_object: Narrative,
    app_spec: AppSpec,
):
    wsid = 123
    job_id = "this_is_a_job_id_to_test"
    narr = test_narrative_object
    get_mock = mocker.patch(
        "narrative_llm_agent.tools.narrative_tools.get_narrative_from_wsid",
        return_value=narr,
    )
    save_mock = mocker.patch(
        "narrative_llm_agent.tools.narrative_tools.save_narrative", return_value=[]
    )
    state_dict = load_test_data_json(Path("app_spec_data") / "app_spec_job_state.json")
    # Digging into too many details here, but good enough.
    config = get_config()
    mock_kbase_jsonrpc_1_call(config.ee_endpoint, state_dict)
    mock_kbase_jsonrpc_1_call(config.nms_endpoint, [app_spec.model_dump()])
    num_cells = len(test_narrative_object.cells)
    mock_ws = MockWorkspace()
    resp = create_app_cell(
        wsid, job_id, mock_ws, ExecutionEngine(), NarrativeMethodStore()
    )
    assert resp == "success"
    get_mock.assert_called_once_with(wsid, mock_ws)
    save_mock.assert_called_once_with(test_narrative_object, wsid, mock_ws)
    assert len(test_narrative_object.cells) == num_cells + 1
    assert test_narrative_object.cells[-1].cell_type == "code"


def test_get_markdown_text(test_narrative_object: Narrative):
    ws = MockWorkspace()
    assert get_all_markdown_text(123, ws) == [
        md.source for md in test_narrative_object.get_markdown()
    ]


def test_get_narrative_state(
    test_narrative_object: Narrative, mock_kbase_jsonrpc_1_call: Callable
):
    ws = MockWorkspace()
    state_dict = load_test_data_json(Path("app_spec_data") / "app_spec_job_state.json")
    # Digging into too many details here, but good enough.
    config = get_config()
    mock_kbase_jsonrpc_1_call(config.ee_endpoint, state_dict)
    state = get_narrative_state(123, ws, ExecutionEngine())
    print(json.dumps(json.loads(state), indent=4))
    assert isinstance(state, str)
    state_dict = json.loads(state)
    assert {"cells", "metadata", "nbformat", "nbformat_minor"} == set(state_dict.keys())
    assert len(state_dict["cells"]) == len(test_narrative_object.cells)
    for idx, cell in enumerate(state_dict["cells"]):
        assert cell["cell_type"] == test_narrative_object.cells[idx].cell_type
        assert (
            cell["metadata"]["kbase"]["type"]
            == test_narrative_object.cells[idx].to_dict()["metadata"]["kbase"]["type"]
        )


# TODO: failure tests - inaccessible WS, auth fail
