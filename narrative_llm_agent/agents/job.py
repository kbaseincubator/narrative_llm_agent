from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool
import json
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine
from narrative_llm_agent.kbase.clients.narrative_method_store import NarrativeMethodStore
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.util.tool import process_tool_input
from narrative_llm_agent.util.app import (
    get_processed_app_spec_params,
    build_run_job_params
)
import time

class JobInput(BaseModel):
    job_id: str = Field(description="The unique identifier for a job running in the KBase Execution Engine. This must be a 24 character hexadecimal string. This must not be a dictionary or JSON-formatted string.")

class AppInput(BaseModel):
    app_id: str = Field(description="The unique identifier for a KBase app. This must be a string. Most app ids have a single '/' character in them.")

class JobStart(BaseModel):
    narrative_id: int = Field(description="The unique id for a KBase narrative. This should be a number.")
    app_id: str = Field(description="The unique identifier for a KBase app. This must be a string. Most app ids have a single '/' character in them.")
    params: dict = Field(description="The set of parameters to pass to a KBase app. This must be a dictionary. Each key is the parameter id, and each value is the expected value given to each parameter. Values can be lists, strings, or numbers.")

class JobAgent(KBaseAgent):
    role: str = "Job and App Manager"
    goal: str = """Manage app and job running and tracking in the KBase system.
        Start and monitor jobs using the KBase Execution engine."""
    backstory: str = """You are an expert computer engineer. You are responsible for initializing, running, and monitoring
        KBase applications using the Execution Engine. You work with the rest of your crew to run bioinformatics and
        data science analyses, handle job states, and return results."""

    def __init__(self: "JobAgent", token: str, llm: LLM) -> "JobAgent":
        super().__init__(token, llm)
        self.__init_agent()
        self.ee_endpoint = self._service_endpoint + "ee2"
        self.nms_endpoint = self._service_endpoint + "narrative_method_store/rpc"
        self.ws_endpoint = self._service_endpoint + "ws"

    def __init_agent(self: "JobAgent") -> None:
        @tool(args_schema=JobInput, return_direct=False)
        def job_status(job_id: str) -> str:
            """Looks up and returns the status of a KBase job. Returns the status as a
            JSON-formatted string. If the job does not exist, or the user doesn't have
            permission to see the job, this raises a JobError. job_id must be a 24 character
            hexadecimal string. Do not pass in a dictionary or a JSON-formatted string.
            """
            return self._job_status(process_tool_input(job_id, "job_id"))

        @tool(args_schema=JobStart, return_direct=False)
        def start_job(narrative_id: int,
                      app_id: str,
                      params: dict) -> str:
            """This starts a new job in KBase, running the given App with the given
            parameters in the given Narrative. If the app with app_id doesn't exist, this
            raises a AppNotFound error. If the narrative_id doesn't exist, or the user
            doesn't have write access to it, this raises a PermissionsError. If the
            parameters are malformed, or refer to data objects that do not exist, this
            returns a ValueError. If the app starts, this returns a JSON-formatted
            dictionary with cell_id and job_id fields."""
            print("starting start_job tool")
            print(f"narrative_id: {narrative_id}")
            print(f"app_id: {app_id}")
            print(f"params: {params}")

            if isinstance(params, str):
                params = json.loads(params)
            return self._start_job(process_tool_input(narrative_id, "narrative_id"),
                                   process_tool_input(app_id, "app_id"),
                                   params)

        @tool(args_schema=AppInput, return_direct=False)
        def get_app_params(app_id: str) -> str:
            """
            This returns the set of parameters for a KBase app. This is returned as a
            dictionary. If the app_id does not exist in KBase, this raises an AppNotFound
            error.
            """
            return self._get_app_params(app_id)

        @tool(args_schema=JobInput, return_direct=False)
        def monitor_job(job_id: str) -> str:
            """
            This monitors a running job in KBase. It will check the job status every 10 seconds.
            When complete, this returns the final job status as a JSON-formatted string. The
            final state can be either completed or error. This might take some time to run,
            as it depends on the job that is running.
            """
            return self._monitor_job(process_tool_input(job_id, "job_id"))

        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            tools = [ job_status, start_job, get_app_params, monitor_job ],
            llm=self._llm,
            allow_delegation=False,
            memory=True,
        )

    def _job_status(self: "JobAgent", job_id: str, as_str=True) -> str | dict:
        ee = ExecutionEngine(self._token, self.ee_endpoint)
        status = ee.check_job(job_id)
        if as_str:
            return json.dumps(status)
        return status

    def _start_job(self: "JobAgent", narrative_id: int, app_id: str, params: dict) -> str:
        print("starting JobAgent._start_job")
        print(f"narrative_id: {narrative_id}")
        print(f"app_id: {app_id}")
        print(f"params: {params}")
        ee = ExecutionEngine(self._token, endpoint=self.ee_endpoint)
        nms = NarrativeMethodStore(endpoint=self.nms_endpoint)
        ws = Workspace(self._token, endpoint=self.ws_endpoint)
        spec = nms.get_app_spec(app_id)
        job_submission = build_run_job_params(spec, params, narrative_id, ws)
        print(job_submission)
        return ee.run_job(job_submission)

    def _get_app_params(self: "JobAgent", app_id: str) -> str:
        nms = NarrativeMethodStore(endpoint=self.nms_endpoint)
        spec = nms.get_app_spec(app_id, include_full_info=True)
        return json.dumps(get_processed_app_spec_params(spec))

    def _monitor_job(self: "JobAgent", job_id: str) -> str:
        is_complete = False
        while not is_complete:
            status = self._job_status(job_id, as_str=False)
            if status["status"] in ["completed", "error"]:
                is_complete = True
            else:
                time.sleep(10)
        return json.dumps(status)
