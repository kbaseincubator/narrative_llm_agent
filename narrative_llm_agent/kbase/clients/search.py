from typing import List
from narrative_llm_agent.kbase.service_client import ServiceClient
from narrative_llm_agent.config import get_config
from pydantic import BaseModel

class DataObject(BaseModel):
  name: str
  obj_type: str


class NarrativeDocCell(BaseModel):
    desc: str
    cell_type: str


class NarrativeDoc(BaseModel):
    access_group: int
    cells: List[NarrativeDocCell]
    copied: bool | None
    creation_date: str
    creator: str
    data_objects: List[DataObject]
    is_narratorial: bool
    is_public: bool
    modified_at: int
    narrative_title: str
    obj_id: int
    obj_name: str
    obj_type_module: str
    obj_type_version: str
    owner: str
    shared_users: list[str]
    tags: list[str]
    timestamp: int
    total_cells: int
    version: int


class NarrativeSearchResults(BaseModel):
    count: int
    search_time: int
    hits: List[NarrativeDoc]


class Search(ServiceClient):
    _service = "search"
    def __init__(self, endpoint: str = None, token: str = None) -> None:
        if endpoint is None:
            endpoint = get_config().search_endpoint
        super().__init__(endpoint, self._service, token=token)

    def search_narratives(self, owner: str, query: str = None) -> NarrativeSearchResults:
        params = {
            "access": {"only_public": False},
            "filters": {"operator": "AND", "fields": [{"field": "owner", "term": owner}]},
            "paging": {"length": 20, "offset": 0},
            "sorts": [["timestamp", "desc"], ["_score", "desc"]],
            "types": ["KBaseNarrative.Narrative"]
        }

        if query is not None:
            params["search"] = {"query": query, "fields": ["agg_fields"]}
        results = self.make_kbase_jsonrpc_1_call("search_workspace", params)
        return NarrativeSearchResults.model_validate(results)
