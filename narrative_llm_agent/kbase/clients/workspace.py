from ..service_client import ServiceClient
from typing import Any
from copy import deepcopy
from narrative_llm_agent.config import get_config
from narrative_llm_agent.kbase.objects.workspace import ObjectInfo, WorkspaceObjectId, WorkspaceInfo

class Workspace(ServiceClient):
    _service = "Workspace"

    def __init__(self: "Workspace", token: str = None, endpoint: str = None) -> None:
        if endpoint is None:
            endpoint = get_config().ws_endpoint
        super().__init__(endpoint, self._service, token=token)

    def get_workspace_info(self: "Workspace", ws_id: int) -> WorkspaceInfo:
        ws_info = self.simple_call("get_workspace_info", {"id": ws_id})
        return WorkspaceInfo.model_validate(ws_info)

    def list_workspace_objects(
        self: "Workspace", ws_id: int, object_type: str = None, as_dict: bool = False
    ) -> list[list] | list[ObjectInfo]:
        ws_info = self.get_workspace_info(ws_id)
        chunk_size = 10000
        current_max = 0
        objects = []
        while current_max < ws_info.max_objid:
            list_obj_params = {
                "ids": [ws_id],
                "minObjectID": current_max,
                "maxObjectID": current_max + chunk_size,
                "type": object_type,
            }
            objects += self.simple_call("list_objects", list_obj_params)
            current_max += chunk_size + 1
        if not as_dict:
            return objects
        return [ObjectInfo.model_validate(info).model_dump() for info in objects]

    def get_object_info(self: "Workspace", obj_ref: str) -> ObjectInfo:
        obj_info = self.simple_call("get_object_info3", {"objects": [{"ref": obj_ref}],"includeMetadata": 1})
        return ObjectInfo.model_validate(obj_info["infos"][0] + [obj_info["paths"][0]])

    def get_object_upas(
        self: "Workspace", ws_id: int, object_type: str = None
    ) -> list[WorkspaceObjectId]:
        obj_infos = self.list_workspace_objects(ws_id, object_type=object_type)
        return [
            WorkspaceObjectId(ws_id=info[6], obj_id=info[0], version=info[4]) for info in obj_infos
        ]

    def get_objects(
        self: "Workspace", refs: list[str], data_paths: list[str] = None
    ) -> list:
        base_params = {}
        if data_paths is not None:
            base_params["included"] = data_paths

        params_list = [dict(deepcopy(base_params)) | {"ref": ref} for ref in refs]
        return self.simple_call("get_objects2", {"objects": params_list})["data"]

    def save_objects(
        self: "Workspace", ws_id: int, objects: list[Any]
    ) -> list[list[Any]]:
        return self.simple_call("save_objects", {"id": ws_id, "objects": objects})
