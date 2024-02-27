from ..service_client import ServiceClient
from typing import Any
from copy import deepcopy

class WorkspaceObjectId:
    upa: str
    ws_id: int
    obj_id: int
    version: int

    def __init__(self: "WorkspaceObjectId", upa: str) -> None:
        self.upa = upa
        self._process_upa()

    def _process_upa(self: "WorkspaceObjectId"):
        split_upa = self.upa.split("/")
        self.ws_id = int(split_upa[0])
        self.obj_id = int(split_upa[1])
        self.version = int(split_upa[2])

    @classmethod
    def from_upa(cls: "WorkspaceObjectId", upa: str) -> "WorkspaceObjectId":
        return cls(upa)

    @classmethod
    def from_ids(cls: "WorkspaceObjectId", ws_id: int, obj_id: int, version: int) -> "WorkspaceObjectId":
        return cls(f"{ws_id}/{obj_id}/{version}")

    def __repr__(self: "WorkspaceObjectId") -> str:
        return self.upa

    def __str__(self: "WorkspaceObjectId") -> str:
        return self.__repr__()


class WorkspaceObjectInfo:
    upa: WorkspaceObjectId
    raw: list[Any]
    name: str

    def __init__(self: "WorkspaceObjectInfo", info: list[Any]) -> None:
        self.upa = WorkspaceObjectId.from_ids(info[6], info[0], info[4])
        self.raw = info
        self.name = info[1]

    def __repr__(self: "WorkspaceObjectInfo") -> str:
        return f"{self.upa}\t{self.name}\n{self.raw}"


class WorkspaceInfo:
    ws_id: int
    name: str
    owner: str
    mod_date: str
    max_objid: int
    perm: str
    global_read: str
    lock_status: str
    meta: dict[str, str]

    def __init__(self: "WorkspaceInfo", info: list[Any]) -> None:
        self.ws_id = info[0]
        self.name = info[1]
        self.owner = info[2]
        self.mod_date = info[3]
        self.max_objid = info[4]
        self.perm = info[5]
        self.global_read = info[6]
        self.lock_status = info[7]
        self.meta = info[8] or {}

    def __repr__(self: "WorkspaceInfo") -> list[Any]:
        return [
            self.ws_id,
            self.name,
            self.owner,
            self.mod_date,
            self.max_objid,
            self.perm,
            self.global_read,
            self.lock_status,
            self.meta
        ]


class Workspace(ServiceClient):
    default_endpoint: str = "https://kbase.us/services/ws"
    _service = "Workspace"

    def __init__(self: "Workspace", token: str, endpoint: str=default_endpoint) -> None:
        super().__init__(endpoint, self._service, token)

    def get_workspace_info(self: "Workspace", ws_id: int) -> WorkspaceInfo:
        ws_info = self.simple_call("get_workspace_info", {"id": ws_id})
        return WorkspaceInfo(ws_info)

    def list_workspace_objects(self: "Workspace", ws_id: int, object_type: str=None, as_dict: bool=False) -> list[list]:
        ws_info = self.get_workspace_info(ws_id)
        chunk_size = 10000
        current_max = 0
        objects = []
        while current_max < ws_info.max_objid:
            list_obj_params = {
                "ids": [ws_id],
                "minObjectID": current_max,
                "maxObjectID": current_max + chunk_size,
                "type": object_type
            }
            objects += self.simple_call("list_objects", list_obj_params)
            current_max += chunk_size + 1
        if not as_dict:
            return objects
        return [self.obj_info_to_json(info) for info in objects]

    def get_object_upas(self: "Workspace", ws_id: int, object_type: str=None) -> list[WorkspaceObjectId]:
        obj_infos = self.list_workspace_objects(ws_id, object_type=object_type)
        return [WorkspaceObjectId.from_ids(info[6], info[0], info[4]) for info in obj_infos]

    def get_objects(self: "Workspace", refs: list[str], data_paths: list[str]=None) -> dict:
        base_params = {}
        if data_paths is not None:
            base_params["included"] = data_paths

        params_list = [dict(deepcopy(base_params)) | {"ref": ref} for ref in refs]
        return self.simple_call("get_objects2", {"objects": params_list})["data"]

    def save_objects(self: "Workspace", ws_id: int, objects: list[Any]) -> list[list[Any]]:
        return self.simple_call("save_objects", {"id": ws_id, "objects": objects})

    @classmethod
    def obj_info_to_json(cls, obj_info: list[Any]) -> dict[str, Any]:
        return {
            "ws_id": obj_info[6],
            "obj_id": obj_info[0],
            "name": obj_info[1],
            "metadata": obj_info[10],
            "type": obj_info[2],
            "saved": obj_info[3],
            "version": obj_info[4],
            "saved_by": obj_info[5],
            "size_bytes": obj_info[9]
        }
