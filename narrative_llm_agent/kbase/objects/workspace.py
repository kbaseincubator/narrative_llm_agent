import json
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, computed_field, model_validator

class ObjectInfo(BaseModel):
    ws_id: int
    obj_id: int
    version: int
    name: str
    ws_name: str
    type: str
    saved: str
    saved_by: str
    size_bytes: int
    metadata: Optional[Dict[str, str]] = {}
    path: Optional[List[str]] = []

    @model_validator(mode="before")
    @classmethod
    def _unpack_obj_info_list(cls, obj_info: Union[List[Any], Tuple[Any, ...], dict]) -> dict:
        if isinstance(obj_info, (list, tuple)):
            if len(obj_info) != 12 and len(obj_info) != 11:
                raise ValueError("Expected either 11 or 12 items in the object info list")
            converted = {
                "ws_id": obj_info[6],
                "obj_id": obj_info[0],
                "name": obj_info[1],
                "ws_name": obj_info[7],
                "metadata": obj_info[10],
                "type": obj_info[2],
                "saved": obj_info[3],
                "version": obj_info[4],
                "saved_by": obj_info[5],
                "size_bytes": obj_info[9]
            }
            if len(obj_info) == 12:
                converted["path"] = obj_info[11]
            return converted
        else:
            return obj_info

    @computed_field
    def upa(self) -> str:
        return f"{self.ws_id}/{self.obj_id}/{self.version}"

class WorkspaceObjectId(BaseModel):
    upa: Optional[str] = None
    ws_id: Optional[int] = None
    obj_id: Optional[int] = None
    version: Optional[int] = None

    @model_validator(mode='after')
    def validate_and_populate(self):
        if self.upa:
            parts = self.upa.split("/")
            if len(parts) != 3:
                raise ValueError("UPA must have format 'ws_id/obj_id/version'")
            self.ws_id, self.obj_id, self.version = map(int, parts)
        elif None not in (self.ws_id, self.obj_id, self.version):
            self.upa = f"{self.ws_id}/{self.obj_id}/{self.version}"
        else:
            raise ValueError(
                "Either provide `upa` or all of `ws_id`, `obj_id`, and `version`."
            )
        return self

    def __repr__(self) -> str:
        return self.upa

    def __str__(self) -> str:
        return self.upa

class WorkspaceInfo(BaseModel):
    ws_id: int
    name: str
    owner: str
    mod_date: str
    max_objid: int
    perm: str
    global_read: str
    lock_status: str
    meta: Optional[Dict[str, str]] = {}

    @model_validator(mode="before")
    def _unpack_ws_info_list(cls, info: Union[List[Any], Tuple[Any, ...], dict]) -> dict:
        if isinstance(info, (list, tuple)):
            if len(info) != 9:
                raise ValueError("Expected exactly 9 items in the object info list")
            return {
                "ws_id": info[0],
                "name": info[1],
                "owner": info[2],
                "mod_date": info[3],
                "max_objid": info[4],
                "perm": info[5],
                "global_read": info[6],
                "lock_status": info[7],
                "meta": info[8] or {}
            }
        return info

    def __str__(self) -> str:
        return json.dumps(
            [
                self.ws_id,
                self.name,
                self.owner,
                self.mod_date,
                self.max_objid,
                self.perm,
                self.global_read,
                self.lock_status,
                self.meta,
            ]
        )

