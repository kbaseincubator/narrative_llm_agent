import json
from narrative_llm_agent.agents.job import JobAgent
from narrative_llm_agent.kbase.clients.execution_engine import JobState

token = "not_a_token"
def test_init(mock_llm):
    ja = JobAgent(token, mock_llm)
    assert ja.role == "Job and App Manager"

def test_job_status_tool(mock_llm, mock_kbase_jsonrpc_1_call, mock_job_states):
    ja = JobAgent(token, mock_llm)
    for job_id, state in mock_job_states.items():
        mock_kbase_jsonrpc_1_call(ja.ee_endpoint, state)
        expected_job_state = JobState(state)
        assert json.loads(ja._job_status(job_id)) == expected_job_state.to_dict()
        assert ja._job_status(job_id, as_str=False) == expected_job_state
