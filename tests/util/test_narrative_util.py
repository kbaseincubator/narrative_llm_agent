from narrative_llm_agent.util.narrative import NarrativeUtil
from narrative_llm_agent.kbase.clients.workspace import (
    Workspace,
    WorkspaceInfo,
)
from narrative_llm_agent.kbase.service_client import ServerError
import pytest
from typing import Any
from tests.test_data.test_data import get_test_narrative
from narrative_llm_agent.kbase.objects.narrative import Narrative


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
                "is_temporary": "false",
                "method.kb_fastqc/runFastQC/b7ea69cd0fe0f62e45a8e6ea4ddeba3cba17a8d4": "1",
                "job_info": '{"queue_time": 0, "run_time": 0, "running": 0, "completed": 0, "error": 0}',
                "format": "ipynb",
                "name": "My Fancy Narrative",
                "description": "",
                "type": "KBaseNarrative.Narrative",
                "ws_name": "some_ws",
            },
        ]


def test_get_ref_from_wsid():
    nu = NarrativeUtil(MockWorkspace())
    assert nu.get_narrative_ref_from_wsid(666) == "666/1"


def test_get_ref_from_wsid_missing_ws():
    nu = NarrativeUtil(MockWorkspace(missing_ws=True))
    with pytest.raises(ServerError) as exc_info:
        nu.get_narrative_ref_from_wsid(123)
    assert "no workspace with id" in str(exc_info.value)


def test_get_ref_from_wsid_no_narr():
    nu = NarrativeUtil(MockWorkspace(missing_narr_meta=True))
    with pytest.raises(ValueError) as exc_info:
        nu.get_narrative_ref_from_wsid(123)
    assert "No narrative found in workspace 123" in str(exc_info.value)


def test_get_narrative_from_wsid():
    nu = NarrativeUtil(MockWorkspace())
    narr = nu.get_narrative_from_wsid(123)
    assert isinstance(narr, Narrative)


def test_get_narrative_from_wsid_wrong_type():
    nu = NarrativeUtil(MockWorkspace(wrong_narr_type=True))
    with pytest.raises(ValueError) as exc_info:
        nu.get_narrative_from_wsid(123)
    assert "The object with reference 123/1 is not a KBase Narrative" in str(
        exc_info.value
    )


def test_get_narrative_from_wsid_missing_ws():
    pass


def test_get_narrative_from_wsid_no_narr():
    pass


def test_save_narrative(mocker):
    ws_id = 123
    mocker.patch.object(
        Workspace, "get_workspace_info", return_value=MockWorkspaceInfo(ws_id)
    )
    mocker.patch.object(Workspace, "save_objects", return_value=[["my", "info"]])
    fake_ws = Workspace("fake", "not_an_endpoint")
    nu = NarrativeUtil(fake_ws)
    narr = Narrative(get_test_narrative(as_dict=True))
    obj_info = nu.save_narrative(narr, ws_id)
    # spot check since it's all fake anyway
    assert obj_info == ["my", "info"]
    # assert obj_info[0] == 1
    # assert obj_info[6] == ws_id
    # assert obj_info[9]["creator"] == "me"
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
        "is_temporary",
        "format",
        "name",
        "description",
        "type",
        "ws_name",
        "data_dependencies",
        "job_info",
    ]
    for key in expected_keys:
        assert key in obj["meta"]
