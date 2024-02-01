from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool
import json
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine

from narrative_llm_agent.tools.job_tools import job_status

class JobInput(BaseModel):
    job_id: str = Field(description="""The unique identifier for a job running in the KBase Execution Engine.""")

class JobAgent(KBaseAgent):
    role: str = "Job Manager"
    goal: str = """Manage app and job running and tracking in the KBase system.
    Start and monitor jobs using the KBase Execution engine.""",
    backstory: str = """You are an expert computer engineer. You are responsible for initializing, running, and monitoring
    KBase applications using the Execution Engine. You work with the rest of your crew to run bioinformatics and
    data science analyses, handle job states, and return results.""",
    ee_endpoint: str = KBaseAgent._service_endpoint + "ee2"

    def __init__(self: "JobAgent", token: str, llm: LLM) -> "JobAgent":
        super().__init__(token, llm)
        self.__init_agent()

    def __init_agent(self: "JobAgent") -> None:
        @tool(args_schema=JobInput, return_direct=False)
        def job_status(job_id: str) -> str:
            """Looks up and returns the status of a KBase job. Returns the status as a
            JSON-formatted string. If the job does not exist, or the user doesn't have
            permission to see the job, this raises a JobError.
            """
            return self._job_status(job_id)

        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            tools = [ job_status ],
            llm=self._llm,
            allow_delegation=False
        )

    def _job_status(self: "JobAgent", job_id: str) -> str:
        ee = ExecutionEngine(self._token, self.ee_endpoint)
        return json.dumps(ee.check_job(job_id))

def job_agent(llm) -> Agent:
    return Agent(
        role="Job Manager",
        goal="Manage app and job running and tracking in the KBase system. Start and monitor jobs using the KBase Execution engine.",
        backstory="""You are an expert computer engineer. You are responsible for initializing, running, and monitoring
        KBase applications using the Execution Engine. You work with the rest of your crew to run bioinformatics and
        data science analyses, handle job states, and return results.""",
        verbose=True,
        tools=[
            job_status,
        ],
        llm=llm,
        allow_delegation=False
    )
