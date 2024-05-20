from ..service_client import ServiceClient

class NarrativeMethodStore(ServiceClient):
    default_endpoint: str = "https://kbase.us/services/narrative_method_store/rpc"
    _service = "NarrativeMethodStore"

    def __init__(self: "NarrativeMethodStore", endpoint: str=default_endpoint) -> None:
        super().__init__(endpoint, self._service, None)

    def get_app_spec(self: "NarrativeMethodStore", app_id: str, tag: str="release", include_full_info: bool=False) -> dict:
        spec = self.simple_call("get_method_spec", {"ids": [app_id], "tag": tag})[0]
        if include_full_info:
            spec["full_info"] = self.get_app_full_info(app_id, tag=tag)
        return spec

    def get_app_full_info(self: "NarrativeMethodStore", app_id: str, tag: str="release") -> dict:
        return self.simple_call("get_method_full_info", {"ids": [app_id], "tag": tag})[0]

