
from narrative_llm_agent.kbase.dynamic_service_client import DynamicServiceClient


class NarrativeService(DynamicServiceClient):
    def __init__(self, token: str = None):
        super().__init__("NarrativeService", token=token)

    def list_narratorials(self):
        return self.simple_call("list_narratorials", {})

    def create_new_narrative(self, title: str) -> int:
        """
        Hacked together to just make a new empty narrative with a title.
        Returns the workspace id as an int
        """
        response = self.simple_call("create_new_narrative", {"includeIntroCell": 0, "title": title})
        return response["workspaceInfo"]["id"]
