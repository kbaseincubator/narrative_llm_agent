from crewai import Agent
from langchain_core.language_models.llms import LLM

class KBaseAgent:
    agent: Agent
    _token: str
    _llm: LLM
    _service_endpoint: str

    def __init__(self: "KBaseAgent", token: str, llm: LLM, service_endpoint: str="https://ci.kbase.us/services/") -> None:
        self._token = token
        self._llm = llm
        self.agent = None
        self._service_endpoint = service_endpoint
