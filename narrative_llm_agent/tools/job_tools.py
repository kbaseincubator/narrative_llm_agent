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
    * The narrative id
    * The final job status
    * The job id
    * The report object UPA, if any
    * A list of created objects, if any, including their names and UPAs.
    This currently searches the list of Created Objects from the given report
    (if any), and the app parameters for any output objects. So it's really
    up to the app authors to play nicely and populate those things correctly.
    * Job errors, if any

    TODO: Also consider searching the workspace for recently made objects,
    relative to when the app was completed.
    TODO: If the job has errors, the report UPA and created objects should
    probably be empty. "Completed with errors" is a possibility, but I don't
    think many KBase apps support that.
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
            CreatedObject(object_upa=obj_info.upa, object_name=obj_info.name)
        )
    return created_objects


def get_app_created_objects(
    job_state: JobState, nms: NarrativeMethodStore, ws: Workspace
) -> set[CreatedObject]:
    """
    This is a little tricky.
    Given the job_state object (which, at this point, is expected to include both the
    results and input parameters), get the list of newly created objects, and
    return a Set of them.

    Expected output objects in KBase apps are (mostly) created with an object name
    given by a user. This'll be in a parameter from the `get_processed_app_spec_params`
    with a "is_output_object" value of True. This function only looks at those, since
    those are the most reproducible way of figuring out created object references.

    In processing app input parameters to start running the app, some parameter ids can
    change. E.g. this is valid case:
    parameter info
    {
        id: "user_output_name",
        ... rest of info ...
    }

    service mapping
    {
        "input_parameter": "user_output_name",
        "target_property": "output_genome_name"
    }

    The parameters can then be mapped as:
    (passed in from user)
    {
        "user_output_name": "my_new_genome"
    }
    (passed to app)
    {
        "output_genome_name": "my_new_genome"
    }

    So we need two things.
    1. A list of all parameters flagged as output objects
    2. The mapping from user parameter id -> service parameter id

    Then we can extract the created object name, check its existence, and get its UPA.
    """
    # get app spec
    app_spec = AppSpec(**(nms.get_app_spec(job_state.job_input.app_id)))
    app_params = get_processed_app_spec_params(app_spec)
    # start with getting the output parameter ids as a set
    output_params = set()
    for param_id, info in app_params.items():
        if info.get("is_output_object"):
            output_params.add(param_id)
    # convert that set to its mapped counterpart
    mapped_output_params = set()
    if app_spec.behavior.kb_service_input_mapping is not None:
        for mapping in app_spec.behavior.kb_service_input_mapping:
            if mapping.input_parameter in output_params:
                mapped_output_params.add(mapping.target_property)
    params = job_state.job_input.params[0]
    output_names = [params.get(param_id) for param_id in mapped_output_params]
    narrative_id = job_state.job_input.ws_id
    created_objects = set()
    for name in output_names:
        try:
            out_obj_info = ws.get_object_info(f"{narrative_id}/{name}")
            created_objects.add(
                CreatedObject(
                    object_upa=out_obj_info.upa, object_name=out_obj_info.name
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
    """
    Runs a job from end to end. Starts it, creates an app cell for it, monitors the job, and returns
    the CompletedJob object at the end.
    """
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
