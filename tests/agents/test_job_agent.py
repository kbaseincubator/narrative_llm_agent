import json
from typing import Any, Callable

import pytest
from pytest_mock import MockerFixture

from narrative_llm_agent.agents.job import JobAgent
from narrative_llm_agent.kbase.clients.execution_engine import JobState
from narrative_llm_agent.kbase.clients.workspace import WorkspaceInfo, Workspace
from narrative_llm_agent.config import get_config
from pathlib import Path

from narrative_llm_agent.kbase.objects.app_spec import AppSpec
from narrative_llm_agent.tools.job_tools import CompletedJob
from tests.conftest import MockLLM
from tests.test_data.test_data import load_test_data_json


@pytest.fixture
def mock_nms_client(mocker: MockerFixture):
    return mocker.patch("narrative_llm_agent.agents.job.NarrativeMethodStore")


@pytest.fixture
def mock_ee_client(mocker: MockerFixture):
    return mocker.patch("narrative_llm_agent.agents.job.ExecutionEngine")


@pytest.fixture
def mock_ws_client(mocker: MockerFixture):
    return mocker.patch("narrative_llm_agent.agents.job.Workspace")


def test_init(mock_llm: MockLLM):
    ja = JobAgent(mock_llm)
    assert ja.role == "Job and App Manager"


def test_job_status_tool(
    mock_llm: MockLLM,
    mock_kbase_jsonrpc_1_call: Callable,
    mock_job_states: dict[str, dict[str, Any]],
):
    ja = JobAgent(mock_llm)
    for job_id, state in mock_job_states.items():
        mock_kbase_jsonrpc_1_call(get_config().ee_endpoint, state)
        expected_job_state = JobState(state)
        assert json.loads(ja._job_status(job_id)) == expected_job_state.to_dict()
        assert ja._job_status(job_id, as_str=False) == expected_job_state


def test_get_app_params_tool(mock_llm: MockLLM, app_spec: AppSpec, mock_nms_client):
    mock_nms = mock_nms_client.return_value
    mock_nms.get_app_spec.return_value = app_spec.model_dump()
    expected_params_path = Path("app_spec_data") / "app_spec_processed_params.json"
    params_spec = load_test_data_json(expected_params_path)
    ja = JobAgent(mock_llm)
    assert json.loads(ja._get_app_params("some_app_id")) == params_spec


def test_start_job_tool(
    mock_llm: MockLLM,
    app_spec: AppSpec,
    mock_nms_client,
    mock_ee_client,
    mock_ws_client,
):
    job_id = "fake_job_id"
    narrative_id = 123
    app_id = app_spec.info.id
    params_path = Path("app_spec_data") / "test_app_spec_inputs.json"
    params = load_test_data_json(params_path)

    mock_nms = mock_nms_client.return_value
    mock_nms.get_app_spec.return_value = app_spec.model_dump()

    mock_ee = mock_ee_client.return_value
    mock_ee.run_job.return_value = job_id

    mock_ws = mock_ws_client.return_value
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
    ja = JobAgent(mock_llm)
    assert ja._start_job(narrative_id, app_id, params) == job_id


def test_monitor_job_tool(mock_llm: MockLLM, mock_ee_client, mock_job_states, mocker):
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
        job_id = job_id,
        job_status = "completed",
        created_objects=[],
        job_error=None,
        report_upa=None
    )
    mocker.patch("narrative_llm_agent.agents.job.summarize_completed_job", return_value = mock_complete_job)
    mock_ee = mock_ee_client.return_value
    mock_ee.check_job.side_effect = fake_check_job
    ja = JobAgent(mock_llm)
    assert ja._monitor_job(job_id, interval=1) == mock_complete_job
