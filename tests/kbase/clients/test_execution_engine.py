import re
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine, JobState
import pytest
from narrative_llm_agent.config import get_config, get_kbase_auth_token


@pytest.fixture
def client():
    return ExecutionEngine()


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


def test_build_client_from_config(client, mock_token):
    assert client._endpoint == get_config().ee_endpoint
    assert client._headers["Authorization"] == mock_token


token = "not_a_token"
endpoint = "https://nope.kbase.us/services/not_ee2"
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
            "endpoint": get_config().ee_endpoint,
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
            "endpoint": get_config().ee_endpoint,
            "token": get_kbase_auth_token(),
        },
    ),
]


@pytest.mark.parametrize("config, expected", configs)
def test_build_client_from_config_with_params(config, expected):
    client = ExecutionEngine(**config)
    assert client._endpoint == expected["endpoint"]
    assert client._headers["Authorization"] == expected["token"]


class TestJobState:
    def test_normal(self, mock_job_states):
        job_id = "job_id_1"
        expected_json = mock_job_states[job_id]
        state = JobState(expected_json)
        assert state.job_id == job_id
        assert state.batch_job is False
        assert state.error is None
        for zero_attr in [
            "queued",
            "estimating",
            "running",
            "finished",
            "updated",
            "retry_count",
        ]:
            assert getattr(state, zero_attr) == 0
        for none_attr in [
            "batch_id",
            "error",
            "error_code",
            "errormsg",
            "terminated_code",
        ]:
            assert getattr(state, none_attr) is None

    def test_error_on_start(self, mock_job_states):
        job_id = "job_id_1"
        reqd_keys = ["job_id", "status"]
        for key in reqd_keys:
            copy_json = mock_job_states[job_id].copy()
            del copy_json[key]
            with pytest.raises(
                KeyError, match=re.escape(f"JobState data is missing required field(s) {key}")
            ):
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
