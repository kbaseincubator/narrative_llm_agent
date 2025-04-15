import json
from pathlib import Path
from typing import Any, Callable

from pytest_mock import MockerFixture
from narrative_llm_agent.kbase.clients.workspace import Workspace, WorkspaceInfo
from narrative_llm_agent.kbase.objects.app_spec import AppSpec
from narrative_llm_agent.tools.job_tools import (
    CreatedObject,
    CompletedJob,
    monitor_job,
    start_job,
    summarize_completed_job,
    get_job_status,
)
from narrative_llm_agent.config import get_config
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine, JobState
from narrative_llm_agent.kbase.clients.narrative_method_store import (
    NarrativeMethodStore,
)
import pytest
from tests.test_data.test_data import load_test_data_json


@pytest.fixture
def mock_nms(mocker: MockerFixture):
    nms = mocker.Mock(spec=NarrativeMethodStore)
    nms.get_app_spec.return_value = load_test_data_json(
        Path("app_spec_data") / "fake_app_spec.json"
    )
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
            "result": [{"report_ref": "1000/6/1", "report_name": "some_app_report"}],
            "id": "12345",
        },
        "wsid": 1000,
        "created": 1740073655000,
        "queued": 1740073656144,
        "running": 1740073667463,
        "finished": 1740073793172,
        "job_input": {
            "method": "fake_app.run_fake_app",
            "app_id": "fake_app/run_fake_app",
            "params": [
                {
                    "input_ws": 1000,
                    "input_object_upa": "1000/4/1",
                    "output_object_name": "new_genome",
                }
            ],
            "source_ws_objects": ["1000/4/1"],
            "meta": {},
            "ws_id": 1000,
            "narrative_cell_info": {
                "cell_id": "f51528ba-0912-4b3a-abde-1154896bcde7",
                "run_id": "047f3969-ff35-447e-afee-fefa1cbbdc2e",
                "app_version_tag": "release",
            },
            "service_ver": "332506c1b0b98d7f3589779c94e187019883ab66",
        },
    }
    job_state = JobState(js_dict)
    cj = summarize_completed_job(job_state, mock_nms, mock_workspace)
    assert isinstance(cj, CompletedJob)
    assert cj.job_error is None
    assert cj.job_id == job_state.job_id
    assert cj.job_status == job_state.status
    assert cj.report_upa == "1000/6/1"
    assert cj.created_objects == [
        CreatedObject(object_upa="1000/5/1", object_name="new_genome")
    ]


def test_job_status_tool(
    mock_kbase_jsonrpc_1_call: Callable,
    mock_job_states: dict[str, dict[str, Any]],
):
    for job_id, state in mock_job_states.items():
        mock_kbase_jsonrpc_1_call(get_config().ee_endpoint, state)
        expected_job_state = JobState(state)
        ee = ExecutionEngine()
        assert json.loads(get_job_status(job_id, ee)) == expected_job_state.to_dict()
        assert get_job_status(job_id, ee, as_str=False) == expected_job_state


def test_monitor_job_tool(mock_job_states: dict[str, dict[str, Any]], mocker: MockerFixture):
    global check_counter
    check_counter = 0
    job_id = "job_id_1"

    def fake_check_job(job_id):
        global check_counter
        state = mock_job_states[job_id].copy()
        if check_counter == 0:
            state["status"] = "queued"
        elif check_counter == 1:
            state["status"] = "running"
        else:
            state["status"] = "completed"
        check_counter += 1
        return JobState(state)

    mock_complete_job = CompletedJob(
        job_id=job_id,
        job_status="completed",
        narrative_id=123,
        created_objects=[],
        job_error=None,
        report_upa=None,
    )
    mocker.patch(
        "narrative_llm_agent.tools.job_tools.summarize_completed_job",
        return_value=mock_complete_job,
    )
    mock_ee = mocker.Mock(spec=ExecutionEngine)
    mock_ee.check_job.side_effect = fake_check_job
    mock_nms = mocker.Mock(spec=NarrativeMethodStore)
    mock_ws = mocker.Mock(spec=Workspace)
    assert (
        monitor_job(job_id, mock_ee, mock_nms, mock_ws, interval=1) == mock_complete_job
    )


def test_start_job_tool(app_spec: AppSpec, mocker: MockerFixture):
    job_id = "fake_job_id"
    narrative_id = 123
    app_id = app_spec.info.id
    params_path = Path("app_spec_data") / "test_app_spec_inputs.json"
    params = load_test_data_json(params_path)

    mock_nms = mocker.Mock(spec=NarrativeMethodStore)
    mock_nms.get_app_spec.return_value = app_spec.model_dump()

    mock_ee = mocker.Mock(spec=ExecutionEngine)
    mock_ee.run_job.return_value = job_id

    mock_ws = mocker.Mock(spec=Workspace)
    mock_ws.get_workspace_info.return_value = WorkspaceInfo(
        [1000, "test_workspace", "test_user", "12345", 100, "a", "n", "n", {}]
    )
    mock_ws.get_object_info.return_value = Workspace.obj_info_to_json(
        [
            2,
            "some_object",
            "KBaseGenomes.Genome-1.0",
            "2024-02-02T17:55:23+0000",
            3,
            "me",
            1,
            "my_narrative",
            "768202029fa4440b217d6c7a41a27a58",
            1089,
            {},
        ]
    )
    assert start_job(narrative_id, app_id, params, mock_ee, mock_nms, mock_ws) == job_id
