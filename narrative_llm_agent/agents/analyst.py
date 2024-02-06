from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM

class AnalystAgent(KBaseAgent):
    role="Computational Biologist and Geneticist"
    goal="Analyze and interpret datasets, and make suggestions into next analysis steps."
    backstory="""You are an expert academic computational biologist with decades of
    experience working in microbial genetics. You have published several genome announcement
    papers and have worked extensively with novel sequence data. You understand the most
    common workflows for assembling new genomes from sequence data. You have implemented and
    published these workflows in the KBase Narrative Interface for use by yourself and others.
    You are highly motivated to produce deep analytical insights from data results."""

    def __init__(self: "AnalystAgent", token: str, llm: LLM):
        super().__init__(token, llm)
        self.__init_agent()

    def __init_agent(self):
        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            allow_delegation=True,
            llm=self._llm
        )
