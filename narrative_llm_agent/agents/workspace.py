from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool
import json
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine
from narrative_llm_agent.util.workspace import WorkspaceUtil
from narrative_llm_agent.util.tool import process_tool_input
from narrative_llm_agent.config import get_config

class NarrativeInput(BaseModel):
    narrative_id: int = Field(description="The narrative id. Should be numeric.")

class UpaInput(BaseModel):
    upa: str = Field(description="""An object UPA (unique permanent address)
                     representing the location of a Workspace data object.
                     Should be a string of the format ws_id/obj_id/ver.
                     For example, '11/22/33'.""")

class JobInput(BaseModel):
    job_id: str = Field(description="""The unique identifier for a job running
                        in the KBase Execution Engine. This must be a 24 character
                        hexadecimal string. This must not be a dictionary or
                        JSON-formatted string.""")

class WorkspaceAgent(KBaseAgent):
    role: str = "Workspace Manager"
    goal: str = "Retrieve data from the KBase Narrative. Filter and interpret datasets as necessary to achieve team goals."
    backstory: str = """You are an expert in bioinformatics and data science, with years of experience working with the DoE KBase system.
    You are responsible for interacting with the KBase system on behalf of your crew.
    These interactions will include uploading and downloading data, running analyses, and retrieving results.
    You are closely familiar with the Workspace service and all of its functionality."""

    def __init__(self: "WorkspaceAgent", token: str, llm: LLM) -> "WorkspaceAgent":
        super().__init__(token, llm)
        self._config = get_config()
        self.__init_agent()

    def __init_agent(self: "WorkspaceAgent"):
        @tool(args_schema=NarrativeInput, return_direct=False)
        def list_objects(narrative_id: int) -> str:
            """Fetch a list of objects available in a KBase Narrative. This returns a JSON-formatted
            list of all objects in a narrative. The narrative_id input must be an integer. Do not
            pass in a dictionary or a JSON-formatted string."""
            return self._list_objects(process_tool_input(narrative_id, "narrative_id"))

        @tool(args_schema=UpaInput, return_direct=False)
        def get_report(upa: str) -> str:
            """Fetch a report object from a KBase Narrative. This returns the full report in plain text.
            It should be an informational summary of the result of a bioinformatics application. The upa
            input must be a string with format number/number/number. Do not input a dictionary or a
            JSON-formatted string. This might take a moment to run, as it fetches data from a database."""
            return self._get_report(process_tool_input(upa, "upa"))

        @tool(args_schema=JobInput, return_direct=False)
        def get_report_from_job_id(job_id: str) -> str:
            """Fetch a report object from a KBase Narrative.
            """
            return self._get_report_from_job_id(process_tool_input(job_id, "job_id"))

        @tool(args_schema=UpaInput, return_direct=False)
        def get_object(upa: str) -> str:
            """Fetch a particular object from a KBase Narrative. This returns a JSON-formatted data object
            from the Workspace service. Its format is dependent on the data type. The upa input must be a
            string with format number/number/number. Do not input a dictionary or a JSON-formatted string."""
            return self._get_object(process_tool_input(upa, "upa"))

        self.agent = Agent(
            role = self.role,
            goal = self.goal,
            backstory = self.backstory,
            verbose = True,
            tools = [
                list_objects,
                get_object,
                get_report,
                get_report_from_job_id,
            ],
            llm=self._llm,
            allow_delegation=False,
            memory=True,
        )

    def _list_objects(self: "WorkspaceAgent", narrative_id: int) -> str:
        """
        Fetches the list of objects in a narrative. Returns the object
        list as stringified JSON.
        narrative_id - int - the id of the narrative (workspace)
        """
        ws = Workspace(self._token, endpoint=self._config.ws_endpoint)
        return json.dumps(ws.list_workspace_objects(narrative_id))

    def _get_object(self: "WorkspaceAgent", upa: str) -> dict:
        """
        Fetches a single object from the workspace service. Returns it
        as a dictionary, structured as per the object type.
        """
        ws = Workspace(self._token, endpoint=self._config.ws_endpoint)
        return ws.get_objects([upa])[0]

    def _get_report(self: "WorkspaceAgent", upa: str) -> str:
        """
        Fetches a report object from the workspace service. If it is not
        a report, this raises a ValueError.
        """
        ws_util = WorkspaceUtil(self._token)
        return ws_util.get_report(upa)

    def _get_report_from_job_id(self: "WorkspaceAgent", job_id: str) -> str:
        """
        Uses the job id to fetch a report from the workspace service.
        This fetches the job information from the Execution Engine service first.
        If the job is not complete, this returns a string saying so.
        If the job is complete, but there is no report object in the output, this returns a
        string saying so.
        If the job is complete and has a report in its outputs, this tries to fetch
        the report using the UPA of the report object.
        """
        ee = ExecutionEngine(self._token, endpoint=self._config.ee_endpoint)
        state = ee.check_job(job_id)
        if state.status in ["queued", "running"]:
            return "The job is not yet complete"
        if state.status in ["terminated", "error"]:
            return "The job did not finish successfully, so there is no report to return."
        if state.status != "completed":
            return f"Unknown job status '{state.status}'"
        if state.job_output is not None:
            # look for report_ref or report_name. Maybe just name?
            # Note: I checked out all app specs in production - report_ref and report_name are both
            # used as "magic values" in the narrative to denote a report object. So really we just need
            # to look for the report_ref one. They're both present in each app that makes a report.
            # So, we need to some sifting here
            if "result" in state.job_output and isinstance(state.job_output["result"], list):
                if "report_ref" in state.job_output["result"][0]:
                    return self._get_report(state.job_output["result"][0]["report_ref"])
                else:
                    return "No report object was found in the job results."
            else:
                return "The job output seems to be malformed, there is no 'result' field."
        return "The job was completed, but no job output was found."
