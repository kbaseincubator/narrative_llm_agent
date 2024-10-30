from narrative_llm_agent.kbase.service_client import ServerError, ServiceClient
import pytest
import json

endpoint = "https://ci.kbase.us/services/fakeservice"
service = "fake_service"
token = "not_a_token"


@pytest.fixture
def client():
    return ServiceClient(endpoint, service, token)


def test_service_client_ok(mock_kbase_jsonrpc_1_call, client):
    expected = {"some": "stuff"}
    mock_kbase_jsonrpc_1_call(endpoint, expected)
    resp = client.simple_call("some_fn", [])
    assert resp == expected


def test_service_client_500(mock_kbase_jsonrpc_1_call, client):
    error = {
        "name": "BigFail",
        "code": 666,
        "message": "Biiiig bada boom.",
        "error": "server fall down.",
    }
    mock_kbase_jsonrpc_1_call(endpoint, error, status_code=500)
    with pytest.raises(ServerError) as exc_info:
        client.simple_call("some_fn", [])
    serv_err = exc_info.value
    assert serv_err.name == error["name"]
    assert serv_err.code == error["code"]
    assert serv_err.message == error["message"]
    assert serv_err.data == error["error"]


def test_service_client_malformed_error(mock_kbase_jsonrpc_1_call, client):
    error = {"some": "error"}
    response_json = mock_kbase_jsonrpc_1_call(endpoint, error, status_code=500)
    with pytest.raises(ServerError) as exc_info:
        client.simple_call("some_fn", [])
    serv_err = exc_info.value
    assert str(serv_err) == f"Unknown: 0. {json.dumps(response_json)}\n"


def test_service_client_malformed_response(mock_kbase_jsonrpc_1_call, client):
    mock_kbase_jsonrpc_1_call(endpoint, {}, no_result=True)
    with pytest.raises(ServerError) as exc_info:
        client.simple_call("some_fn", [])
    assert str(exc_info.value) == "Unknown: 0. An unknown server error occurred\n"
