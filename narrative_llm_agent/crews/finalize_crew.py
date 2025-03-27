from narrative_llm_agent.agents.analyst import AnalystAgent
from narrative_llm_agent.agents.narrative import NarrativeAgent
from crewai import Crew, Task, LLM
from crewai.crews import CrewOutput

class FinalizeCrew:
    _token: str
    _llm: LLM
    _crew_results: list[CrewOutput]

    def __init__(self, llm: LLM, token: str = None) -> None:
        self._token = token
        self._llm = llm
        self._analyst = AnalystAgent(llm, "openai/gpt-4o")
        self._narrative = NarrativeAgent(llm, token=token)
        self._agents = [
            self._analyst.agent,
            self._narrative.agent,
        ]
        self._crew_results = []
        self._outputs = []

    def finalize_narrative(self, narrative_id: int, app_list: list[dict[str, str]]) -> CrewOutput:
        tasks = self.build_tasks(narrative_id, app_list)
        crew = Crew(
            agents=self._agents,
            tasks=tasks,
            verbose=True,
        )
        results = crew.kickoff()
        self._crew_results.append(results)
        return self._crew_results[-1]

    def build_tasks(self, narrative_id: int, app_list: list[dict[str, str]]) -> list[Task]:
        summarize_task_prompt = f"""
        Your task is to cleanup the finalized narrative. This involves the following steps.
        1. Extract the text from all markdown cells in the narrative with id {narrative_id}. These will contain the report summaries. Do not run an app for this.
        2. Summarize these report summaries together in the context of the provided goals of the narrative project and the apps that were run: {app_list}. There should be one markdown cell for each task, and one at the beginning stating the goals.
        3. Format this summary as markdown. It should have the tone of a scientific publication. Write this text as though you are the scientist performing the work - avoid language like "the user performed...". Don't just concatenate the different summaries together, but process and interpret them given the context.
        """
        summarize_task = Task(
            description=summarize_task_prompt,
            expected_output="A summary of narrative completion.",
            agent=self._analyst.agent
        )

        store_summary_task = Task(
            description=f"Store the summary result as markdown in the given narrative with id {narrative_id}, then return it.",
            expected_output="A summary of the narrative completion.",
            agent=self._narrative.agent,
            context=[summarize_task]
        )

        return [
            summarize_task,
            store_summary_task
        ]
