from crewai import Agent
from langchain_core.language_models.llms import LLM


class KBaseAgent:
    agent: Agent | None
    _token: str | None
    _llm: LLM

    def __init__(self: "KBaseAgent", llm: LLM, token: str = None) -> None:
        self.agent = None
        self._llm = llm
        self._token = token
