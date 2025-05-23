from typing import Any, Optional
from narrative_llm_agent.tools.app_tools import get_app_params
from narrative_llm_agent.tools.job_tools import (
    CompletedJob,
    get_job_status,
    run_job
)
from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from pydantic import BaseModel, Field
from crewai.tools import tool
import json
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine
from narrative_llm_agent.kbase.clients.narrative_method_store import (
    NarrativeMethodStore,
)
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.util.tool import process_tool_input
from langchain_community.agent_toolkits.load_tools import load_tools

class JobInput(BaseModel):
    job_id: str = Field(
        description="The unique identifier for a job running in the KBase Execution Engine. This must be a 24 character hexadecimal string. This must not be a dictionary or JSON-formatted string."
    )


class AppInput(BaseModel):
    app_id: str = Field(
        description="The unique identifier for a KBase app. This must be a string. Most app ids have a single '/' character in them."
    )


class JobStart(BaseModel):
    narrative_id: int = Field(
        description="The unique id for a KBase narrative. This should be a number."
    )
    app_id: str = Field(
        description="The unique identifier for a KBase app. This must be a string. Most app ids have a single '/' character in them."
    )
    params: dict = Field(
        description="The set of parameters to pass to a KBase app. This must be a dictionary. Each key is the parameter id, and each value is the expected value given to each parameter. Values can be lists, strings, or numbers."
    )


class AppStartInfo(BaseModel):
    narrative_id: int
    app_id: str
    app_params: dict[str, Any]


class AppOutputInfo(BaseModel):
    app_id: str
    output_object_upa: Optional[str] = None
    output_object_name: Optional[str] = None
    report_upa: Optional[str] = None
    app_error: Optional[str] = None
    narrative_id: int


class CompletedJobAndReport(BaseModel):
    job_info: CompletedJob
    report: Optional[str] = None

class JobAgent(KBaseAgent):
    role: str = "Job and App Manager"
    goal: str = """Manage app and job running and tracking in the KBase system.
        Start and monitor jobs using the KBase Execution engine."""
    backstory: str = """You are an expert computer engineer. You are responsible for initializing, running, and monitoring
        KBase applications using the Execution Engine. You work with the rest of your crew to run bioinformatics and
        data science analyses, handle job states, and return results."""

    def __init__(self: "JobAgent", llm: LLM, token: str = None) -> "JobAgent":
        super().__init__(llm, token=token)
        self.__init_agent()

    def __init_agent(self: "JobAgent") -> None:
        human_tools = load_tools(["human"])

        @tool("job status")
        def get_job_status_tool(job_id: str) -> str:
            """Looks up and returns the status of a KBase job. Returns the status as a
            JSON-formatted string. If the job does not exist, or the user doesn't have
            permission to see the job, this raises a JobError. job_id must be a 24 character
            hexadecimal string. Do not pass in a dictionary or a JSON-formatted string.
            """
            return get_job_status(process_tool_input(job_id, "job_id"), ExecutionEngine(token=self._token))


        @tool("get app parameters")
        def get_app_params_tool(app_id: str) -> str:
            """
            This returns the set of parameters for a KBase app. This is returned as a
            stringified dictionary. If the app_id does not exist in KBase, this raises
            an AppNotFound error.
            """
            return json.dumps(get_app_params(app_id, NarrativeMethodStore()))

        @tool("run job")
        def run_job_tool(narrative_id: int, app_id: str, params: dict) -> CompletedJob:
            """
            This starts and runs a job in KBase. Once the job starts, it checks the status
            every 10 seconds. When complete, this returns the job information including
            the final status, list of any created objects, and report UPA.
            This might take some time to run, as it depends on the job that is running.
            """
            if isinstance(params, str):
                params = json.loads(params)
            return run_job(
                process_tool_input(narrative_id, "narrative_id"),
                process_tool_input(app_id, "app_id"),
                params,
                ExecutionEngine(token=self._token),
                NarrativeMethodStore(),
                Workspace(token=self._token),
            )

        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            tools=[
                get_job_status_tool,
                get_app_params_tool,
                run_job_tool,
            ],  # + human_tools,
            llm=self._llm,
            allow_delegation=False,
            memory=True,
        )
