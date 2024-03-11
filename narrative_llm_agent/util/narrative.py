import json

from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.objects.narrative import (
    NARRATIVE_ID_KEY,
    NARRATIVE_TYPE,
    Narrative,
    is_narrative,
)


class NarrativeUtil:
    _ws: Workspace

    def __init__(self, ws_client: Workspace):
        self._ws = ws_client

    def get_narrative_ref_from_wsid(self, ws_id: int) -> str:
        """
        Gets the object reference of a Narrative, in the format 'ws_id/obj_id'.
        This uses the workspace metadata to find the narrative object id
        and combine it with the workspace id.
        """
        ws_info = self._ws.get_workspace_info(ws_id)
        if NARRATIVE_ID_KEY not in ws_info.meta:
            raise ValueError(f"No narrative found in workspace {ws_id}")

        return f"{ws_id}/{ws_info.meta[NARRATIVE_ID_KEY]}"

    def get_narrative_from_wsid(self, ws_id: int) -> Narrative:
        """
        Returns a Narrative object from the workspace with the given ws_id.
        """
        narr_ref = self.get_narrative_ref_from_wsid(ws_id)
        narr_obj = self._ws.get_objects([narr_ref])[0]
        if not is_narrative(narr_obj["info"][2]):
            raise ValueError(f"The object with reference {narr_ref} is not a KBase Narrative.")
        return Narrative(narr_obj["data"])

    def save_narrative(self, narrative: Narrative, ws_id: int) -> list:
        """
        Saves a narrative object as a new version.
        TODO: update metadata properly.
        TODO: move this to the Narrative Service (maybe).
        """
        narr_ref = self.get_narrative_ref_from_wsid(ws_id)
        obj_id = narr_ref.split("/")[-1]
        narr_obj = narrative.to_dict()
        ws_save_obj = {
            "type": NARRATIVE_TYPE,
            "data": narr_obj,
            "objid": obj_id,
            "meta": self._build_save_metadata(narrative),
            "provenance": [
                {
                    "service": "narrative_llm_agent",
                    "description": "Saved by a KBase Assistant",
                    "service_ver": "0.0.1",  # TODO: put this somewhere reasonable
                }
            ],
        }
        obj_info = self._ws.save_objects(ws_id, [ws_save_obj])[0]
        return obj_info

    def _build_save_metadata(self, narrative: Narrative) -> dict[str, str]:
        """
        Builds metadata to be saved with the object.
        Needs to be in string-string key-value-pairs for the Workspace service to allow it.
        """
        narr_meta = narrative.metadata
        string_keys = [
            "creator",
            "is_temporary",
            "format",
            "name",
            "description",
            "type",
            "ws_name",
        ]
        obj_keys = {
            "data_dependencies": [],
            "job_info": {"queue_time": 0, "run_time": 0, "running": 0, "completed": 0, "error": 0},
        }
        meta = {}
        for key in string_keys:
            meta[key] = narr_meta.raw.get(key)
        for key in obj_keys:
            if key in narr_meta.raw:
                meta[key] = json.dumps(narr_meta.raw.get(key))
            else:
                meta[key] = json.dumps(obj_keys[key])
        cell_counts = narrative.get_cell_counts()
        for key in cell_counts:
            meta[key] = str(cell_counts[key])
        return meta
