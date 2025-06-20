from pathlib import Path
import pytest
from narrative_llm_agent.crews.job_crew import JobCrew
from narrative_llm_agent.tools.job_tools import CompletedJob
from narrative_llm_agent.kbase.objects.workspace import ObjectInfo
from narrative_llm_agent.kbase.clients.narrative_method_store import NarrativeMethodStore
from crewai import Task

from tests.test_data.test_data import load_test_data_json

@pytest.fixture
def job_crew(mock_llm):
    return JobCrew(mock_llm, mock_llm, token="fake_token")


def test_initialization(job_crew):
    assert job_crew._token == "fake_token"
    assert isinstance(job_crew._agents, list)
    assert all(agent is not None for agent in job_crew._agents)


def test_build_tasks_returns_list(job_crew, mocker):
    obj_info = ObjectInfo(
        ws_id=1,
        obj_id=2,
        version=3,
        name="some_object",
        ws_name="my_ws",
        type="Module.Object-1.0",
        saved="whenever",
        saved_by="me",
        size_bytes=2
    )
    job_crew._nms = mocker.Mock(spec=NarrativeMethodStore)
    job_crew._nms.get_app_spec.return_value = load_test_data_json(Path("app_spec_data") / "test_app_spec.json")

    tasks = job_crew.build_tasks("prokka/annotate_contigs", 123, obj_info)
    assert isinstance(tasks, list)
    assert all(isinstance(t, Task) for t in tasks)


@pytest.mark.parametrize("app_id, expected_job_id", [
    ("FastQC/run", "fastqc_job"),
    ("Trimmomatic/run", "trimmomatic_job"),
    ("Spades/run", "spades_job"),
    ("Quast/run", "quast_job"),
    ("Prokka/run", "prokka_job"),
    ("CheckM/run", "checkm_job"),
    ("Build_GenomeSet/run", "build_genomeset_job"),
    ("GTDBTk/run", "gtdbtk_job"),
])
def test_start_job_debug_skip(job_crew, app_id, expected_job_id):
    narrative_id = 42
    result = job_crew.start_job_debug_skip("Some App", "1/2/3", narrative_id, app_id)
    assert isinstance(result, CompletedJob)
    assert result.job_id == expected_job_id
    assert result.job_status == "completed"
    assert result.job_error is None
    assert result.narrative_id == narrative_id
