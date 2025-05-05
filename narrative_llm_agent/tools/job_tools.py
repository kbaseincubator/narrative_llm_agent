import time
from pydantic import BaseModel
from narrative_llm_agent.config import get_config
from narrative_llm_agent.kbase.clients.debug_mock import KBaseMock
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine, JobState
from narrative_llm_agent.kbase.clients.narrative_method_store import (
    NarrativeMethodStore,
)
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.objects.app_spec import AppSpec
from narrative_llm_agent.kbase.objects.report import KBaseReport
from narrative_llm_agent.kbase.service_client import ServerError
from narrative_llm_agent.tools.narrative_tools import create_app_cell
from narrative_llm_agent.util.app import (
    build_run_job_params,
    get_processed_app_spec_params,
)
from typing import Optional


class CreatedObject(BaseModel):
    object_upa: str
    object_name: str

    model_config = {"frozen": True}


class CompletedJob(BaseModel):
    job_id: str
    job_status: str
    created_objects: list[CreatedObject] = []
    job_error: Optional[str] = None
    report_upa: Optional[str] = None
    narrative_id: int


def summarize_completed_job(
    job_state: JobState, nms: NarrativeMethodStore, ws: Workspace
) -> CompletedJob:
    """
    This summarizes a completed job with the following information:
    * The report object UPA, if any
    * A list of created objects, if any, including their names and UPAs.
    This currently searches the list of Created Objects from the given report
    (if any), and the app parameters for any output objects. So it's really
    up to the app authors to play nicely and populate those things correctly.

    TODO: Also consider searching the workspace for recently made objects,
    relative to when the app was completed.
    """
    # get the output
    # get the report object
    # get the objects created bit of the report
    # make this structure:
    if job_state.status not in {"completed", "error", "terminated"}:
        raise RuntimeError(f"Job {job_state.job_id} is not complete")

    processed = {
        "job_id": job_state.job_id,
        "job_status": job_state.status,
        "created_objects": set(),
        "narrative_id": job_state.ws_id,
    }
    error = None
    if job_state.status == "error":
        error = job_state.errormsg
    processed["job_error"] = error
    result = {}
    report_upa = None
    if job_state.job_output is not None and "result" in job_state.job_output:
        result = job_state.job_output["result"][0]
        report_upa = result.get("report_ref")
    processed["report_upa"] = report_upa
    if report_upa is not None:
        processed["created_objects"].update(get_report_created_objects(report_upa, ws))
    # check for new object. need app spec.
    processed["created_objects"].update(get_app_created_objects(job_state, nms, ws))
    return CompletedJob(**processed)


def get_report_created_objects(report_upa: str, ws: Workspace) -> set[CreatedObject]:
    report_data = ws.get_objects([report_upa])[0]["data"]
    report = KBaseReport(**report_data)
    created_objects = set()
    for new_object in report.objects_created:
        obj_info = ws.get_object_info(new_object.ref)
        created_objects.add(
            CreatedObject(object_upa=obj_info["upa"], object_name=obj_info["name"])
        )
    return created_objects


def get_app_created_objects(
    job_state: JobState, nms: NarrativeMethodStore, ws: Workspace
) -> set[CreatedObject]:
    # get app spec
    app_spec = AppSpec(**(nms.get_app_spec(job_state.job_input.app_id)))
    app_params = get_processed_app_spec_params(app_spec)
    output_params = []
    for param_id, info in app_params.items():
        if info.get("is_output_object"):
            output_params.append(param_id)
    params = job_state.job_input.params[0]
    output_names = [params[param_id] for param_id in output_params]
    narrative_id = job_state.job_input.ws_id
    created_objects = set()
    for name in output_names:
        try:
            out_obj_info = ws.get_object_info(f"{narrative_id}/{name}")
            created_objects.add(
                CreatedObject(
                    object_upa=out_obj_info["upa"], object_name=out_obj_info["name"]
                )
            )
        except ServerError:
            pass
    return created_objects


def monitor_job(
    job_id: str,
    ee: ExecutionEngine,
    nms: NarrativeMethodStore,
    ws: Workspace,
    interval: int = 10,
) -> CompletedJob:
    is_complete = False
    while not is_complete:
        status = get_job_status(job_id, ee, as_str=False)
        if status.status in ["completed", "error"]:
            is_complete = True
        else:
            time.sleep(interval)
    return summarize_completed_job(status, nms, ws)


def get_job_status(job_id: str, ee: ExecutionEngine, as_str=True) -> str | JobState:
    if get_config().debug:
        status = KBaseMock().check_mock_job(job_id)
    else:
        status = ee.check_job(job_id)
    if as_str:
        return str(status)
    return status


def start_job(
    narrative_id: int,
    app_id: str,
    params: dict,
    ee: ExecutionEngine,
    nms: NarrativeMethodStore,
    ws: Workspace,
) -> str:
    spec = nms.get_app_spec(app_id)
    job_submission = build_run_job_params(AppSpec(**spec), params, narrative_id, ws)
    print("starting job:")
    print(job_submission)
    if get_config().debug:
        return KBaseMock().mock_run_job(narrative_id, app_id, params, job_submission)
    return ee.run_job(job_submission)


def run_job(
    narrative_id: int,
    app_id: str,
    params: dict,
    ee: ExecutionEngine,
    nms: NarrativeMethodStore,
    ws: Workspace
) -> CompletedJob:
    job_id = start_job(narrative_id, app_id, params, ee, nms, ws)
    # TODO have this return an error state as well, for checking. Right now, just letting exceptions go up.
    create_app_cell(
        narrative_id,
        job_id,
        ws,
        ee,
        nms
    )
    return monitor_job(job_id, ee, nms, ws)
