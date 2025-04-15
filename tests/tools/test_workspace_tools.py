
from pytest_mock import MockerFixture
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.tools.workspace_tools import get_object_metadata


def mock_obj_info(upa: str, metadata: dict[str, str] | None) -> dict:
    ws_id, obj_id, ver = upa.split("/")
    return {
        "ws_id": ws_id,
        "obj_id": obj_id,
        "name": "some_obj",
        "ws_name": "some_ws",
        "type": "SomeObject.Test-1.0",
        "saved": 12345,
        "version": ver,
        "saved_by": "user",
        "size_bytes": 12345,
        "metadata": metadata,
    }

def build_mock_ws(mocker: MockerFixture, upa: str, meta: dict[str|str] | None):
    my_obj_info = mock_obj_info(upa, meta)
    mock_ws = mocker.Mock(spec=Workspace)
    mock_ws.get_object_info.return_value = my_obj_info
    return mock_ws


def test_get_obj_metadata_null(mocker: MockerFixture):
    upa = "1/2/3"
    assert get_object_metadata(upa, build_mock_ws(mocker, upa, None)) is None


def test_get_obj_metadata(mocker: MockerFixture):
    upa = "1/2/3"
    meta = {"foo": "bar", "baz": "frobozz"}
    meta_result = get_object_metadata(upa, build_mock_ws(mocker, upa, meta))
    assert meta_result == meta

# TODO: tests for errors, bad upas, missing data, not allowed, etc.
