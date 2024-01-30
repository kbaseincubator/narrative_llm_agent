from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool
from narrative_llm_agent.kbase.clients.workspace import Workspace
import json

class NarrativeInput(BaseModel):
    narrative_id: str = Field(description="The narrative id. Should be numeric.")

class UpaInput(BaseModel):
    upa: str = Field(description="""An object UPA (unique permanent address)
                     representing the location of a Workspace data object.
                     Should be a string of the format ws_id/obj_id/ver.
                     For example, '11/22/33'.""")

@tool(args_schema=NarrativeInput, return_direct=False)
def list_objects(narrative_id: int) -> int:
    """Fetch a list of objects available in a KBase Narrative. This returns a JSON-formatted list of all objects in
    a narrative."""
    ws = Workspace(None, endpoint="https://ci.kbase.us/services/ws")
    return json.dumps(ws.list_workspace_objects(narrative_id))

@tool(args_schema=UpaInput, return_direct=False)
def get_object(upa: str) -> dict:
    """Fetch a particular object from a KBase Narrative. This returns a JSON-formatted data object
    from the Workspace service. Its format is dependent on the data type."""
    ws = Workspace(None, endpoint="https://ci.kbase.us/services/ws")
    return json.dumps(ws.get_objects([upa]))
