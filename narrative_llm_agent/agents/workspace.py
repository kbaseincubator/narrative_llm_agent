from narrative_llm_agent.kbase.clients.blobstore import Blobstore
from narrative_llm_agent.tools.report_tools import get_report, get_report_from_job_id
from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from pydantic import BaseModel, Field
from crewai.tools import tool
import json
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine
from narrative_llm_agent.util.tool import process_tool_input


class NarrativeInput(BaseModel):
    narrative_id: int = Field(description="The narrative id. Should be numeric.")


class UpaInput(BaseModel):
    upa: str = Field(
        description="""An object UPA (unique permanent address)
                     representing the location of a Workspace data object.
                     Should be a string of the format ws_id/obj_id/ver.
                     For example, '11/22/33'."""
    )


class JobInput(BaseModel):
    job_id: str = Field(
        description="""The unique identifier for a job running
                        in the KBase Execution Engine. This must be a 24 character
                        hexadecimal string. This must not be a dictionary or
                        JSON-formatted string."""
    )


class WorkspaceAgent(KBaseAgent):
    role: str = "Workspace Manager"
    goal: str = "Retrieve data from the KBase Narrative. Filter and interpret datasets as necessary to achieve team goals."
    backstory: str = """You are an expert in bioinformatics and data science, with years of experience working with the DoE KBase system.
    You are responsible for interacting with the KBase system on behalf of your crew.
    These interactions will include uploading and downloading data, running analyses, and retrieving results.
    You are closely familiar with the Workspace service and all of its functionality."""

    def __init__(
        self: "WorkspaceAgent", llm: LLM, token: str = None
    ) -> "WorkspaceAgent":
        super().__init__(llm, token=token)
        self.__init_agent()

    def __init_agent(self: "WorkspaceAgent"):
        @tool("list objects")
        def list_objects_tool(narrative_id: int) -> str:
            """Fetch a list of objects available in a KBase Narrative. This returns a JSON-formatted
            list of all objects in a narrative. The narrative_id input must be an integer. Do not
            pass in a dictionary or a JSON-formatted string."""
            ws = Workspace(token=self._token)
            return json.dumps(
                ws.list_workspace_objects(
                    process_tool_input(narrative_id, "narrative_id"), as_dict=True
                )
            )

        @tool("get report")
        def get_report_tool(upa: str) -> str:
            """Fetch a report object from a KBase Narrative. This returns the full report in plain text.
            It should be an informational summary of the result of a bioinformatics application. The upa
            input must be a string with format number/number/number. Do not input a dictionary or a
            JSON-formatted string. This might take a moment to run, as it fetches data from a database."""
            ws = Workspace(token=self._token)
            blobstore = Blobstore(token=self._token)
            return get_report(process_tool_input(upa, "upa"), ws, blobstore)

        @tool("get report from job id")
        def get_report_from_job_id_tool(job_id: str) -> str:
            """Fetch a report object from a KBase Narrative."""
            ws = Workspace(token=self._token)
            ee = ExecutionEngine(token=self._token)
            blobstore = Blobstore(token=self._token)
            return get_report_from_job_id(
                process_tool_input(job_id, "job_id"), ee, ws, blobstore
            )

        @tool("get object")
        def get_object_tool(upa: str) -> dict:
            """Fetch a particular object from a KBase Narrative. This returns a JSON-formatted data object
            from the Workspace service. Its format is dependent on the data type. The upa input must be a
            string with format number/number/number. Do not input a dictionary or a JSON-formatted string."""
            ws = Workspace(token=self._token)
            return ws.get_objects([process_tool_input(upa, "upa")])[0]

        @tool("Get object name")
        def get_object_name_tool(upa: str) -> str:
            """Get the name of a data object from its UPA. This returns the name string. An UPA input must
            be a string with the format number/number/number."""
            ws = Workspace(token=self._token)
            return ws.get_object_info(process_tool_input(upa, "upa"))["name"]

        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            tools=[
                list_objects_tool,
                get_object_tool,
                get_report_tool,
                get_report_from_job_id_tool,
                get_object_name_tool,
            ],
            llm=self._llm,
            allow_delegation=False,
            memory=True,
        )
