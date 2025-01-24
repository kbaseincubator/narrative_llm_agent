from narrative_llm_agent.agents.analyst import AnalystAgent
from narrative_llm_agent.agents.job import JobAgent, AppStartInfo
from narrative_llm_agent.agents.narrative import NarrativeAgent
from narrative_llm_agent.agents.workspace import WorkspaceAgent
from narrative_llm_agent.agents.coordinator import CoordinatorAgent
from narrative_llm_agent.agents.metadata import MetadataAgent
from langchain_core.language_models.llms import LLM
from crewai import Crew, Task

class JobCrew:
    _token: str
    _llm: LLM

    def __init__(self, llm: LLM, token: str = None) -> None:
        self._token = token
        self._llm = llm
        self._analyst = AnalystAgent(llm, token=token)
        self._narr = NarrativeAgent(llm, token=token)
        self._job = JobAgent(llm, token=token)
        self._workspace = WorkspaceAgent(llm, token=token)
        self._coordinator = CoordinatorAgent(llm)
        self._metadata = MetadataAgent(llm, token=token)
        self._agents = [
            self._analyst.agent,
            self._narr.agent,
            self._job.agent,
            self._workspace.agent,
            self._coordinator.agent,
            self._metadata.agent,
        ]

    def start_job(self, app_name: str, reads_upa: str, narrative_id: int) -> None:
        self._tasks = self.build_tasks(app_name, narrative_id, reads_upa)
        crew = Crew(
            agents=self._agents,
            tasks=self._tasks,
            verbose=True,
        )
        self._last_result = crew.kickoff()

    def build_tasks(
        self, app_name: str, narrative_id: int, reads_upa: str
    ) -> list[Task]:
        get_reads_qc_app_task = Task(
            description=f"Get the app id for the KBase {app_name} app. Return only the app id. This can be found in the catalog.",
            expected_output="An app id with the format module/app, with a single forward-slash",
            agent=self._coordinator.agent,
        )

        get_app_params_task = Task(
            description=f"""
            From the given KBase app id, fetch the list of parameters needed to run it. Use the App and Job manager agent
            for assistance. With the knowledge that there is a data object with id "{reads_upa}", populate a dictionary
            with the parameters where the keys are parameter ids, and values are the proper parameter values, or their
            default values if no value can be found or calculated. Return the dictionary of inputs, the app id, and the
            narrative id {narrative_id}  for use in the next task. Do not add comments or other text. The dictionary of
            inputs and the app id must not be combined into a single dictionary.
            """,
            expected_output="A dictionary of parameters used to run the app with the given id along with the narrative id.",
            output_pydantic=AppStartInfo,
            agent=self._coordinator.agent,
        )

        start_job_task = Task(
            description=f"""
            Using the app parameters and app id, use provided tools to start a new KBase app, which will return a job id.
            Use that job id to create a new App Cell in the narrative such that narrative_id={narrative_id}. Return only the
            job id.
            """,
            expected_output="A KBase job id string.",
            agent=self._job.agent,
            context=[get_app_params_task]
        )

        make_app_cell_task = Task(
            description=f"""
            Using the job id, create an app cell in narrative {narrative_id}. The add_app_cell tool is useful here.
            """,
            expected_output="A note with either success or failure of saving the new cell",
            agent=self._narr.agent,
        )

        monitor_job_task = Task(
            description="""
            Using the job id, monitor the progress of the running job. The monitor_job tool is helpful here.
            If completed, continue to the next task. If in an error state, summarize the error for the user and stop.
            """,
            expected_output="Return either a note saying that the job has completed, or a summary of the job error.",
            agent=self._job.agent,
            context=[start_job_task],
        )

        job_completion_task = Task(
            description="""Use a tool to fetch the status of KBase job with the given job id.
            If it is completed without an error, retrieve the job results.
            If the job results contain a reference to a report, with an UPA (a string with format number/number/number),
            return it. Do not add any additional text, just return only the UPA.
            If the job results contain an "error" key, stop and return a message saying an error has occurred.
            Do not return an UPA, only an error message.
            You must always use a tool when interacting with KBase services or databases. If this is delegated, make sure
            the delegated agent uses a tool when interacting with KBase.
            """,
            expected_output="An UPA of the format 'number/number/number', representing the output of a KBase job, or an error.",
            agent=self._job.agent,
            context=[start_job_task],
        )

        report_retrieval_task = Task(
            description="""Using the provided UPA (a string with format number/number/number),
            use a tool to get the report object from the Workspace service. UPAs are unique permanent addresses used to identify data objects.
            The Workspace Manager will be helpful here. Make sure the delegated agent uses a tool for interacting with KBase.
            Return the full report text. Your final answer MUST be the report text.
            """,
            expected_output="The text of a KBase app report object",
            agent=self._workspace.agent,
        )

        report_analysis_task = Task(
            description="""Analyze the report text and derive some insight into the result. Write a brief summary, including bullet points
            when appropriate, formatted in markdown. Your final answer MUST be the summary of the report.""",
            expected_output="A summary of the report from the previous task",
            agent=self._coordinator.agent,
        )

        save_analysis_task = Task(
            description=f"""Save the analysis by adding a markdown cell to the Narrative with id {narrative_id}. The markdown text must
            be the analysis text. If not successful, say so and stop.""",
            expected_output="A note with either success or failure of saving the new cell",
            agent=self._narr.agent,
            extra_content=narrative_id,
        )

        return [
            get_reads_qc_app_task,
            get_app_params_task,
            start_job_task,
            make_app_cell_task,
            monitor_job_task,
            job_completion_task,
            report_retrieval_task,
            report_analysis_task,
            save_analysis_task,
        ]
