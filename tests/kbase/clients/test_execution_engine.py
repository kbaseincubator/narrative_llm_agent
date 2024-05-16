from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine, JobState
import pytest

token = "not_a_token"
endpoint = "https://nope.kbase.us/services/not_ee2"

@pytest.fixture
def client():
    return ExecutionEngine(token, endpoint)

def test_check_job(mock_kbase_client_call, mock_job_states, client):
    for job_id, state in mock_job_states.items():
        mock_kbase_client_call(client, state)
        assert client.check_job(job_id) == JobState(state)
