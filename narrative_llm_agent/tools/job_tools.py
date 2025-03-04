from pydantic import BaseModel
from narrative_llm_agent.kbase.clients.execution_engine import JobState
from narrative_llm_agent.kbase.clients.narrative_method_store import NarrativeMethodStore
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.objects.app_spec import AppSpec
from narrative_llm_agent.kbase.objects.report import KBaseReport
from narrative_llm_agent.kbase.service_client import ServerError
from narrative_llm_agent.util.app import get_processed_app_spec_params


class CreatedObject(BaseModel):
    object_upa: str
    object_name: str

    model_config = {"frozen": True}

class CompletedJob(BaseModel):
    job_id: str
    job_status: str
    created_objects: list[CreatedObject] = []
    job_error: str | None = None
    report_upa: str | None = None

def summarize_completed_job(job_state: JobState, nms: NarrativeMethodStore, ws: Workspace) -> CompletedJob:
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
        "created_objects": set()
    }
    error = None
    if job_state.status == "error":
        error = job_state.errormsg
    processed["job_error"] = error
    result = {}
    report_upa = None
    if "result" in job_state.job_output:
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
        created_objects.add(CreatedObject(object_upa = obj_info["upa"], object_name = obj_info["name"]))
    return created_objects

def get_app_created_objects(job_state: JobState, nms: NarrativeMethodStore, ws: Workspace) -> set[CreatedObject]:
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
            created_objects.add(CreatedObject(object_upa = out_obj_info["upa"], object_name = out_obj_info["name"]))
        except ServerError:
            pass
    return created_objects
