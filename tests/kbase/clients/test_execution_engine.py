from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine
import pytest

token = "not_a_token"
endpoint = "https://nope.kbase.us/services/not_ee2"

@pytest.fixture
def client():
    return ExecutionEngine(token, endpoint)

def test_check_job(mock_kbase_client_call, client):
    expected = {"status": "ok"}
    mock_kbase_client_call(client, expected)
    assert client.check_job("foo") == expected

