from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool
import json
from narrative_llm_agent.kbase.clients.workspace import Workspace


class NarrativeInput(BaseModel):
    narrative_id: int = Field(description="The narrative id. Should be numeric.")

class UpaInput(BaseModel):
    upa: int = Field(description="""An object UPA (unique permanent address)
                     representing the location of a Workspace data object.
                     Should be a string of the format ws_id/obj_id/ver.
                     For example, '11/22/33'.""")


class NarrativeAgent(KBaseAgent):
    role: str = "Workspace Manager"
    goal: str = "Retrieve data from the KBase Narrative. Filter and interpret datasets as necessary to achieve team goals."
    backstory: str = """You are an expert in bioinformatics and data science, with years of experience working with the DoE KBase system.
    You are responsible for interacting with the KBase system on behalf of your crew.
    These interactions will include uploading and downloading data, running analyses, and retrieving results.
    You are closely familiar with the Workspace service and all of its functionality."""
    ws_endpoint: str = KBaseAgent._service_endpoint + "ws"

    def __init__(self: "NarrativeAgent", token: str, llm: LLM) -> "NarrativeAgent":
        super().__init__(token, llm)
        self.__init_agent()

    def __init_agent(self: "NarrativeAgent"):
        @tool(args_schema=NarrativeInput, return_direct=False)
        def list_objects(narrative_id: int) -> str:
            """Fetch a list of objects available in a KBase Narrative. This returns a JSON-formatted list of all objects in
            a narrative. The narrative_id input must be an integer. Do not pass in a dictionary or a string."""
            return self._list_objects(narrative_id)

        @tool(args_schema=UpaInput, return_direct=False)
        def get_object(object_id: int) -> str:
            """Fetch a particular object from a KBase Narrative. This returns a JSON-formatted data object
            from the Workspace service. Its format is dependent on the data type."""
            return self._get_object(object_id)

        self.agent = Agent(
            role = self.role,
            goal = self.goal,
            backstory = self.backstory,
            verbose = True,
            tools = [
                list_objects,
                get_object
            ],
            llm=self._llm,
            allow_delegation=False
        )

    def _list_objects(self: "NarrativeAgent", narrative_id: int) -> str:
        ws = Workspace(self._token, endpoint=self.ws_endpoint)
        return json.dumps(ws.list_workspace_objects(narrative_id))

    def _get_object(self: "NarrativeAgent", upa: str) -> str:
        ws = Workspace(self._token, endpoint=self.ws_endpoint)
        return json.dumps(ws.get_objects([upa]))
