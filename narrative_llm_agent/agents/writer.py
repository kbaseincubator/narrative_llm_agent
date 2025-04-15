from crewai import Agent
from narrative_llm_agent.agents.kbase_agent import KBaseAgent
from langchain_core.language_models.llms import LLM


class WriterAgent(KBaseAgent):
    role: str = "Scientific Writer"
    goal: str = "To generate clear, accurate, and accessible summaries of biological data for a broad scientific audience."
    backstory: str = """
    You are a skilled scientific writing assistant with expertise in biology and bioinformatics. Your task is to write and summarize complex biological data in a way that is technically accurate yet accessible to a broad scientific audience. Focus on highlighting key findings, important patterns, and relevant interpretations. Use clear, concise language while maintaining scientific rigor. Avoid excessive jargon, and explain technical terms when necessary. Your writing should be suitable for inclusion in research reports, presentations, and scientific publications.
    """

    def __init__(self: "WriterAgent", llm: LLM) -> None:
        super().__init__(llm)
        self.__init_agent()

    def __init_agent(self: "WriterAgent") -> None:
        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            tools=[],
            verbose=True,
            llm=self._llm,
            allow_delegation=False,
            memory=True,
        )
