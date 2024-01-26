from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool
from narrative_llm_agent.kbase.clients.workspace import Workspace
import json

class NarrativeInput(BaseModel):
    narrative_id: str = Field(description="The narrative id. Should be numeric.")

@tool(args_schema=NarrativeInput, return_direct=False)
def fetch_narrative_objects(narrative_id: int) -> int:
    """Fetch a list of objects available in a KBase Narrative. This returns a JSON-formatted list of all objects in
    a narrative."""
    print(f"My narrative id = '{narrative_id}' and stuff")
    ws = Workspace(None, endpoint="https://ci.kbase.us/services/ws")
    return json.dumps(ws.list_workspace_objects(narrative_id))
