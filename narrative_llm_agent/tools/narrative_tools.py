import json
from typing import Any
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine
from narrative_llm_agent.kbase.clients.narrative_method_store import (
    NarrativeMethodStore,
)
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.objects.narrative import (
    NARRATIVE_ID_KEY,
    NARRATIVE_TYPE,
    Narrative,
    is_narrative,
)


def get_narrative_state(
    narrative_id: int, ws: Workspace, ee: ExecutionEngine
) -> dict[str, Any]:
    narr = get_narrative_from_wsid(narrative_id, ws)
    return narr.get_current_state(ee)


def get_narrative_ref_from_wsid(ws_id: int, ws: Workspace) -> str:
    """
    Gets the object reference of a Narrative, in the format 'ws_id/obj_id'.
    This uses the workspace metadata to find the narrative object id
    and combine it with the workspace id.
    """
    ws_info = ws.get_workspace_info(ws_id)
    if NARRATIVE_ID_KEY not in ws_info.meta:
        raise ValueError(f"No narrative found in workspace {ws_id}")

    return f"{ws_id}/{ws_info.meta[NARRATIVE_ID_KEY]}"


def get_narrative_from_wsid(ws_id: int, ws: Workspace) -> Narrative:
    """
    Returns a Narrative object from the workspace with the given ws_id.
    """
    narr_ref = get_narrative_ref_from_wsid(ws_id, ws)
    narr_obj = ws.get_objects([narr_ref])[0]
    if not is_narrative(narr_obj["info"][2]):
        raise ValueError(
            f"The object with reference {narr_ref} is not a KBase Narrative."
        )
    return Narrative(narr_obj["data"])


def create_markdown_cell(narrative_id: int, text: str, ws: Workspace) -> str:
    """Stores results of a conversation in a Narrative markdown cell. This uses the narrative id
    to pull the narrative from the workspace, create the new markdown cell at the bottom,
    and save it again. It returns a simple message when complete, or throws an Exception if it
    fails."""
    narr = get_narrative_from_wsid(narrative_id, ws)
    narr.add_markdown_cell(text)
    save_narrative(narr, narrative_id, ws)
    return "Conversation successfully stored."


def create_app_cell(
    narrative_id: int,
    job_id: str,
    ws: Workspace,
    ee: ExecutionEngine,
    nms: NarrativeMethodStore,
):
    """
    Add an app cell to the Narrative object and save it. This uses the job id to look
    up all the app information required to rebuild an app cell. It adds the cell to the
    bottom of the narrative in the state it was in during the last check. If successful,
    this returns the string 'success'.
    """
    job_state = ee.check_job(job_id)
    app_spec = nms.get_app_spec(job_state.job_input.app_id)

    narr = get_narrative_from_wsid(narrative_id, ws)
    narr.add_app_cell(job_state, app_spec)
    save_narrative(narr, narrative_id, ws)
    return "success"


def save_narrative(narrative: Narrative, ws_id: int, ws: Workspace) -> list:
    """
    Saves a narrative object as a new version.
    TODO: update metadata properly.
    TODO: move this to the Narrative Service (maybe).
    """
    narr_ref = get_narrative_ref_from_wsid(ws_id, ws)
    obj_id = narr_ref.split("/")[-1]
    narr_obj = narrative.to_dict()
    ws_save_obj = {
        "type": NARRATIVE_TYPE,
        "data": narr_obj,
        "objid": obj_id,
        "meta": _build_save_metadata(narrative),
        "provenance": [
            {
                "service": "narrative_llm_agent",
                "description": "Saved by a KBase Assistant",
                "service_ver": "0.0.1",  # TODO: put this somewhere reasonable
            }
        ],
    }
    obj_info = ws.save_objects(ws_id, [ws_save_obj])[0]
    return obj_info


def _build_save_metadata(narrative: Narrative) -> dict[str, str]:
    """
    Builds metadata to be saved with the object.
    Needs to be in string-string key-value-pairs for the Workspace service to allow it.
    """
    narr_meta = narrative.metadata
    string_keys = [
        "creator",
        "format",
        "name",
        "description",
    ]
    obj_keys = {
        "data_dependencies": [],
        "job_info": {
            "queue_time": 0,
            "run_time": 0,
            "running": 0,
            "completed": 0,
            "error": 0,
        },
    }
    meta = {}
    for key in string_keys:
        meta[key] = narr_meta.raw.get(key, "")
    for key in obj_keys:
        if key in narr_meta.raw:
            meta[key] = json.dumps(narr_meta.raw.get(key))
        else:
            meta[key] = json.dumps(obj_keys[key])
    cell_counts = narrative.get_cell_counts()
    for key in cell_counts:
        meta[key] = str(cell_counts[key])
    return meta


def get_all_markdown_text(narrative_id: int, ws: Workspace) -> list[str]:
    narr = get_narrative_from_wsid(narrative_id, ws)
    md_cells = narr.get_markdown()
    return [cell.source for cell in md_cells]
