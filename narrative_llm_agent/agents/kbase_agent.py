from crewai import Agent
from langchain_core.language_models.llms import LLM

class KBaseAgent:
    _agent: Agent
    _token: str
    _llm: LLM
    #TODO Make config, env variable, or other.
    _service_endpoint: str = "https://ci.kbase.us/services/"

    def __init__(self: "KBaseAgent", token: str, llm: LLM) -> "KBaseAgent":
        self._token = token
        self._llm = llm
