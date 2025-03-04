from pathlib import Path
from typing import Any
from narrative_llm_agent.tools.job_tools import (
    CreatedObject,
    CompletedJob,
    summarize_completed_job,
    get_report_created_objects,
    get_app_created_objects
)
from narrative_llm_agent.kbase.clients.execution_engine import JobState
from narrative_llm_agent.kbase.clients.narrative_method_store import NarrativeMethodStore
import pytest
from tests.test_data.test_data import load_test_data_json

@pytest.fixture
def mock_nms(mocker):
    nms = mocker.Mock(spec=NarrativeMethodStore)
    nms.get_app_spec.return_value = load_test_data_json(Path("app_spec_data") / "fake_app_spec.json")
    yield nms

def test_summarize_completed_job_incomplete(mock_job_states: dict[str, dict[str, Any]]):
    running_job_state = JobState(mock_job_states["job_id_2"])
    with pytest.raises(RuntimeError, match="Job job_id_2 is not complete"):
        summarize_completed_job(running_job_state, None, None)

def test_summarize_completed_job_ok(mock_workspace, mock_nms):
    js_dict = {
        "job_id": "some_job",
        "user": "some_user",
        "status": "completed",
        "job_output": {
            "version": "1.1",
            "result": [{
                "report_ref": "1000/6/1",
                "report_name": "some_app_report"
            }],
            "id": "12345"
        },
        "wsid": 1000,
        "created":1740073655000,
        "queued": 1740073656144,
        "running": 1740073667463,
        "finished": 1740073793172,
        "job_input": {
            "method": "fake_app.run_fake_app",
            "app_id": "fake_app/run_fake_app",
            "params": [{
                "input_ws": 1000,
                "input_object_upa": "1000/4/1",
                "output_object_name": "new_genome",
            }],
            "source_ws_objects": ["1000/4/1"],
            "meta": {},
            "ws_id": 1000,
            "narrative_cell_info": {
                "cell_id": "f51528ba-0912-4b3a-abde-1154896bcde7",
                "run_id": "047f3969-ff35-447e-afee-fefa1cbbdc2e",
                "app_version_tag": "release"
            },
            "service_ver": "332506c1b0b98d7f3589779c94e187019883ab66"
        },
    }
    job_state = JobState(js_dict)
    cj = summarize_completed_job(job_state, mock_nms, mock_workspace)
    assert isinstance(cj, CompletedJob)
    assert cj.job_error is None
    assert cj.job_id == job_state.job_id
    assert cj.job_status == job_state.status
    assert cj.report_upa == "1000/6/1"
    assert cj.created_objects == [CreatedObject(object_upa = "1000/5/1", object_name = "new_genome")]
