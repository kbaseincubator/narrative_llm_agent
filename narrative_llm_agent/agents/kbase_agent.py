from crewai import Agent
from langchain_core.language_models.llms import LLM

class KBaseAgent:
    agent: Agent
    _token: str
    _llm: LLM

    def __init__(self: "KBaseAgent", token: str, llm: LLM) -> None:
        self._token = token
        self._llm = llm
        self.agent = None
