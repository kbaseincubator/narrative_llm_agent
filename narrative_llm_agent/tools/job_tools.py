from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine
import json

class JobInput(BaseModel):
    job_id: str = Field(description="""The unique identifier for a job running in the KBase Execution Engine.""")

@tool(args_schema=JobInput, return_direct=False)
def job_status(job_id: str) -> str:
    """Looks up and returns the status of a KBase job. Returns the status as a
    JSON-formatted string. If the job does not exist, or the user doesn't have
    permission to see the job, this raises a JobError.
    """
    ee = ExecutionEngine(None, endpoint="https://ci.kbase.us/services/ee2")
    return json.dumps(ee.check_job(job_id))
