import json
from narrative_llm_agent.agents.job import JobAgent

token = "not_a_token"
def test_init(mock_llm):
    wa = JobAgent(token, mock_llm)
    assert wa.role == "Job and App Manager"

def test_job_status_tool(mock_llm, mock_kbase_jsonrpc_1_call):
    wa = JobAgent(token, mock_llm)
    job_id = "some_job_id"
    expected_response = {
        "job_id": job_id,
        "status": "complete",
        "user": "some_user",
        "wsid": "12345",
        "job_input": {
            "method": "",
            "app_id": "",
            "params": [],
            "service_ver": "0.0.1"
        },
    }
    mock_kbase_jsonrpc_1_call(wa.ee_endpoint, expected_response)
    assert json.loads(wa._job_status(job_id)) == expected_response
