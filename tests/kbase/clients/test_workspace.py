from narrative_llm_agent.config import get_config, get_kbase_auth_token
from narrative_llm_agent.kbase.clients.workspace import (
    Workspace,
    WorkspaceInfo,
    WorkspaceObjectId,
)

import pytest

from narrative_llm_agent.kbase.objects.workspace import ObjectInfo


@pytest.fixture
def ws_client():
    return Workspace()


token = "not_a_token"
endpoint = "https://nope.kbase.us/services/not_ws"
configs = [
    (
        {
            "endpoint": endpoint,
            "token": token,
        },
        {
            "endpoint": endpoint,
            "token": token,
        },
    ),
    (
        {"token": token},
        {
            "endpoint": get_config().ws_endpoint,
            "token": token,
        },
    ),
    (
        {
            "endpoint": endpoint,
        },
        {
            "endpoint": endpoint,
            "token": get_kbase_auth_token(),
        },
    ),
    (
        {},
        {
            "endpoint": get_config().ws_endpoint,
            "token": get_kbase_auth_token(),
        },
    ),
]


@pytest.mark.parametrize("config, expected", configs)
def test_build_client_from_config_with_params(config, expected):
    client = Workspace(**config)
    assert client._endpoint == expected["endpoint"]
    assert client._headers["Authorization"] == expected["token"]


def test_get_ws_info(mock_kbase_client_call, ws_client):
    ws_id = 123
    ws_info = [ws_id, "my_workspace", "me", "some_date", 11000, "o", "n", "n", {}]
    mock_kbase_client_call(ws_client, ws_info)
    expected_info = WorkspaceInfo.model_validate(ws_info)
    ret_info = ws_client.get_workspace_info(ws_id)
    assert str(expected_info) == str(ret_info)


def test_list_workspace_objects(mock_kbase_client_call, ws_client):
    """
    Need to cheat here a little bit as we're mocking two different calls.
    This would be opaque to the user, but as we're testing the client (and not mocking
    it), we gotta break that black box testing a touch. :P
    """
    ws_id = 123456
    ws_info = [ws_id, "mine", "me", "123", 3, "o", "n", "n", {}]
    expected_infos = [
        [
            1,
            "foo1",
            "Object.Type",
            "123",
            4,
            "me",
            123456,
            "nope",
            "noway",
            1231234,
            {"some": "meta"},
        ],
        [
            2,
            "foo2",
            "Object.Type",
            "123",
            5,
            "me",
            123456,
            "nope",
            "noway",
            1231234,
            {"some": "meta"},
        ],
        [
            3,
            "foo3",
            "Object.Type",
            "123",
            6,
            "me",
            123456,
            "nope",
            "noway",
            1231234,
            {"some": "meta"},
        ],
    ]
    mock_kbase_client_call(ws_client, ws_info, "get_workspace_info")
    mock_kbase_client_call(ws_client, expected_infos, "list_objects")
    received = ws_client.list_workspace_objects(ws_id)
    for idx, obj_info in enumerate(received):
        assert obj_info == expected_infos[idx]

    received = ws_client.list_workspace_objects(ws_id, as_dict=True)
    for idx, obj_info in enumerate(received):
        assert obj_info == ObjectInfo.model_validate(obj_info).model_dump()


def test_get_object_upas(mock_kbase_client_call, ws_client):
    """
    Also cheating here. See test_list_workspace_objects.
    """
    ws_id = 123456
    ws_info = [ws_id, "mine", "me", "123", 3, "o", "n", "n", {}]
    object_infos = [
        [
            1,
            "foo1",
            "Object.Type",
            "123",
            4,
            "me",
            123456,
            "nope",
            "noway",
            1231234,
            {"some": "meta"},
        ],
        [
            2,
            "foo2",
            "Object.Type",
            "123",
            5,
            "me",
            123456,
            "nope",
            "noway",
            1231234,
            {"some": "meta"},
        ],
        [
            3,
            "foo3",
            "Object.Type",
            "123",
            6,
            "me",
            123456,
            "nope",
            "noway",
            1231234,
            {"some": "meta"},
        ],
    ]
    expected = [
        WorkspaceObjectId(upa="123456/1/4"),
        WorkspaceObjectId(upa="123456/2/5"),
        WorkspaceObjectId(upa="123456/3/6")
    ]
    mock_kbase_client_call(ws_client, ws_info, "get_workspace_info")
    mock_kbase_client_call(ws_client, object_infos, "list_objects")
    received = ws_client.get_object_upas(ws_id)
    for idx, upa in enumerate(received):
        assert str(upa) == str(expected[idx])


def test_get_objects(mock_kbase_client_call, ws_client):
    """
    #TODO this should include a mock that checks / asserts based around
    the full parameter formatting, and possibly the object result.
    i.e. the params should look like:
    {
        "objects": [{
            "included": [data_paths],
            "ref": ref1
        }, {
            "included": [data_paths],
            "ref": ref2
        }]
    }
    and the result should look like:
    {
        "data": [
            {"info": [object info tuple], "data": { data dictionary }, "provenance": [ provenances ]},
            ...
        ]
    }
    but this should be left for integration tests, maybe
    """
    refs = ["1/2/3", "4/5/6"]
    expected_objs = [{"obj1": "stuff"}, {"obj2": "stuff"}]
    mock_kbase_client_call(ws_client, {"data": expected_objs})
    assert ws_client.get_objects(refs) == expected_objs
    assert ws_client.get_objects(refs, ["some/data/paths"]) == expected_objs


def test_save_objects(mock_kbase_client_call, ws_client):
    """
    Returns an object info in real life. For the unit test, we're kinda testing
    a no-op, ensuring that the request is well-formed and the client responds
    to a response by passing it forward.
    I mean, we could craft a whole response based on the data inputs and
    make up some size_bytes field and so on, but it's not worth it.
    If we ever do some integration tests, that belongs there.
    """
    obj_info = [
        1,
        "foo",
        "bar",
        "123",
        2,
        "me",
        3,
        "nope",
        "noway",
        1231234,
        {"some": "meta"},
    ]
    mock_kbase_client_call(ws_client, [obj_info])
    assert ws_client.save_objects(3, [{"myobject": "lives_here"}]) == [obj_info]


def test_get_object_info(mock_kbase_client_call, ws_client):
    obj_info = [
        1,
        "foo",
        "bar",
        "123",
        2,
        "me",
        3,
        "nope",
        "noway",
        1231234,
        {"some": "meta"},
    ]
    path = []
    mock_kbase_client_call(ws_client, {"infos": [obj_info], "paths": [path]})
    processed_info = ObjectInfo.model_validate(obj_info + [path])
    assert ws_client.get_object_info("3/1/2") == processed_info
