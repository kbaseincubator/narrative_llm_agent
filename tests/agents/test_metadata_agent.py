from narrative_llm_agent.agents.metadata import (
    MetadataAgent,
    Workspace,
    NarrativeUtil
)
import json
import pytest

token = "NotAToken"

def mock_obj_info(upa: str, metadata: dict[str, str]|None) -> dict:
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
        "metadata": metadata
    }

@pytest.fixture
def mock_ws_client(mocker):
    return mocker.patch("narrative_llm_agent.agents.job.Workspace")

def test_init(mock_llm):
    ma = MetadataAgent(token, mock_llm)
    assert ma.role == "Human Interaction Manager"


def test_get_obj_metadata_null(mock_llm, mocker):
    upa = "1/2/3"
    my_obj_info = mock_obj_info(upa, None)
    mock = mocker.patch.object(Workspace, "get_object_info", return_value=my_obj_info)
    ma = MetadataAgent(token, mock_llm)
    assert ma._get_object_metadata(upa) == "null"
    mock.assert_called_once_with(upa)

def test_get_obj_metadata(mock_llm, mocker):
    upa = "1/2/3"
    meta = {"foo": "bar", "baz": "frobozz"}
    my_obj_info = mock_obj_info(upa, meta)
    mock = mocker.patch.object(Workspace, "get_object_info", return_value=my_obj_info)
    ma = MetadataAgent(token, mock_llm)
    meta_str = ma._get_object_metadata(upa)
    assert json.loads(meta_str) == meta
    mock.assert_called_once_with(upa)

# TODO: tests for errors, bad upas, missing data, not allowed, etc.

def test_store_conversation(mock_llm, mocker, test_narrative_object):
    ws_id = 123
    conversation = json.dumps({"some": "chat", "results": "here"})
    narr = test_narrative_object
    get_mock = mocker.patch.object(NarrativeUtil, "get_narrative_from_wsid", return_value=narr)
    save_mock = mocker.patch.object(NarrativeUtil, "save_narrative", return_value=[])
    num_cells = len(narr.cells)
    ma = MetadataAgent(token, mock_llm)
    resp = ma._store_conversation(ws_id, conversation)
    assert resp == "Conversation successfully stored."
    get_mock.assert_called_once_with(ws_id)
    save_mock.assert_called_once_with(narr, ws_id)
    assert len(narr.cells) == num_cells + 1
    assert narr.cells[-1].source == conversation

# TODO: tests for errors, bad ws_id, non-string conversations
