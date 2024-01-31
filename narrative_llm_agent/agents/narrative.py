from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool
import json
from narrative_llm_agent.kbase.clients.workspace import Workspace


class NarrativeInput(BaseModel):
    narrative_id: str = Field(description="The narrative id. Should be numeric.")

class UpaInput(BaseModel):
    upa: str = Field(description="""An object UPA (unique permanent address)
                     representing the location of a Workspace data object.
                     Should be a string of the format ws_id/obj_id/ver.
                     For example, '11/22/33'.""")


class NarrativeAgent(KBaseAgent):
    role: str = "Bioinformaticist and Data Scientist"
    goal: str = "Retrieve data from the KBase system. Filter and interpret datasets as necessary to achieve team goals."
    backstory: str = """You are an expert in bioinformatics and data science, with years of experience working with the DoE KBase system.
    You are responsible for interacting with the KBase Narrative interface on behalf of your crew.
    These interactions will include uploading and downloading data, running analyses, and retrieving results."""

    def __init__(self: "NarrativeAgent", token: str, llm: LLM):
        super().__init__(token, llm)
        self.__init_agent()

    def __init_agent(self: "NarrativeAgent"):
        self._agent = Agent(
            role = self.role,
            goal = self.goal,
            backstory = self.backstory,
            verbose = True,
            tools = [
                self.list_objects.__get__(self, NarrativeAgent),
                self.get_object.__get__(self, NarrativeAgent)
            ],
            llm=self._llm,
            allow_delegation=False
        )

    @tool(args_schema=NarrativeInput, return_direct=False)
    def list_objects(self: "NarrativeAgent", narrative_id: int) -> int:
        """Fetch a list of objects available in a KBase Narrative. This returns a JSON-formatted list of all objects in
        a narrative. The narrative_id input must be an integer. Do not pass in a dictionary or a string."""
        ws = Workspace(self._token, endpoint=self._service_endpoint + "ws")
        return json.dumps(ws.list_workspace_objects(narrative_id))

    @tool(args_schema=UpaInput, return_direct=False)
    def get_object(self: "NarrativeAgent", upa: str) -> dict:
        """Fetch a particular object from a KBase Narrative. This returns a JSON-formatted data object
        from the Workspace service. Its format is dependent on the data type."""
        ws = Workspace(self._token, endpoint=self._service_endpoint + "ws")
        return json.dumps(ws.get_objects([upa]))





    # def narrative_agent(llm) -> Agent:
    #     return Agent(
    #         role="Bioinformaticist and Data Scientist",
    #         goal="Retrieve data from the KBase system. Filter and interpret datasets as necessary to achieve team goals.",
    #         backstory="""You are an expert in bioinformatics and data science, with years of experience working with the DoE KBase system.
    #         You are responsible for interacting with the KBase Narrative interface on behalf of your crew.
    #         These interactions will include uploading and downloading data, running analyses, and retrieving results.""",
    #         verbose=True,
    #         tools=[
    #             list_objects,
    #             get_object
    #         ],
    #         llm=llm,
    #         allow_delegation=False
    #     )
