from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine, JobState
import pytest

token = "not_a_token"
endpoint = "https://nope.kbase.us/services/not_ee2"

@pytest.fixture
def client():
    return ExecutionEngine(token, endpoint)

class TestExecutionEngineClient:
    def test_check_job(self, mock_kbase_client_call, mock_job_states, client):
        for job_id, state in mock_job_states.items():
            mock_kbase_client_call(client, state)
            assert client.check_job(job_id) == JobState(state)

    def test_run_job(self, mock_kbase_client_call, client):
        ret_job_id = "some_new_job_id"
        mock_kbase_client_call(client, ret_job_id)
        # TODO: kind of a null test. might need some introspection
        assert client.run_job({}) == ret_job_id

class TestJobState:
    def test_normal(self, mock_job_states):
        job_id = "job_id_1"
        expected_json = mock_job_states[job_id]
        state = JobState(expected_json)
        assert state.job_id == job_id
        assert state.batch_job is False
        assert state.error is None
        for zero_attr in ["queued", "estimating", "running", "finished", "updated", "retry_count"]:
            assert getattr(state, zero_attr) == 0
        for none_attr in ["batch_id", "error", "error_code", "errormsg", "terminated_code"]:
            assert getattr(state, none_attr) is None

    def test_error_on_start(self, mock_job_states):
        job_id = "job_id_1"
        reqd_keys = ["job_id", "user", "wsid", "status", "job_input"]
        for key in reqd_keys:
            copy_json = mock_job_states[job_id].copy()
            del copy_json[key]
            with pytest.raises(KeyError, match=f"JobState data is missing required field\(s\) {key}"):
                JobState(copy_json)

    def test_error_state(self, mock_job_states):
        job_id = "job_error"
        state = JobState(mock_job_states[job_id])
        assert state.error.error == "some error"
        assert state.error.name == "error name"
        assert state.error.code == 42
        assert state.error.message == "totally an error"
        assert state.errormsg == "an error message"
        assert state.error_code == 500
