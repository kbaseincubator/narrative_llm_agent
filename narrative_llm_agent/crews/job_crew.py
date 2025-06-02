from narrative_llm_agent.agents.job import JobAgent, AppStartInfo
from narrative_llm_agent.agents.narrative import NarrativeAgent
from narrative_llm_agent.agents.workspace import WorkspaceAgent
from narrative_llm_agent.agents.coordinator import CoordinatorAgent
from narrative_llm_agent.agents.writer import WriterAgent
from narrative_llm_agent.agents.metadata import MetadataAgent
from langchain_core.language_models.llms import LLM
from crewai import Crew, Task
from crewai.crew import CrewOutput

from narrative_llm_agent.tools.job_tools import CompletedJob, CreatedObject

class JobCrew:
    """
    Initializes and runs a CrewAI Crew that will run a single KBase job from start to finish,
    analyze, and interpret the results, saving a summary in a Narrative.

    TODO: add context from the original metadata task
    TODO: add context from previous app runs
    TODO: add some context about the input object and goals of the app run
    """
    _token: str
    _llm: LLM
    _crew_results: list

    def __init__(self, workflow_llm: LLM, writer_llm: LLM, token: str = None) -> None:
        self._crew_results = []
        self._token = token
        self._narr = NarrativeAgent(workflow_llm, token=token)
        self._job = JobAgent(workflow_llm, token=token)
        self._workspace = WorkspaceAgent(workflow_llm, token=token)
        self._coordinator = CoordinatorAgent(workflow_llm)
        self._metadata = MetadataAgent(workflow_llm, token=token)
        self._writer = WriterAgent(writer_llm)
        self._agents = [
            self._narr.agent,
            self._job.agent,
            self._workspace.agent,
            self._coordinator.agent,
            self._metadata.agent,
            self._writer.agent
        ]

    def start_job(self, app_name: str, input_object_upa: str, narrative_id: int, app_id: str|None=None) -> CrewOutput:
        """
        Starts the job from a given app name (note this isn't the ID. Name like "Prokka" not id like "ProkkaAnnotation/annotate_contigs")
        and input object to be run in a given narrative.
        """
        # TODO: convert UPA to name, pass both to build_tasks
        self._tasks = self.build_tasks(app_name, narrative_id, input_object_upa, app_id)
        crew = Crew(
            agents=self._agents,
            tasks=self._tasks,
            verbose=True,
        )
        self._crew_results.append(crew.kickoff())
        return self._crew_results[-1]

    def start_job_debug_skip(self, app_name: str, input_object_upa: str, narrative_id: int, app_id: str|None=None) -> str:
        """
        A debugger that just returns the result of a fake run to see if the next step is processed correctly.
        """
        inputs = f"app name: {app_name}\ninput_object_upa: {input_object_upa}\nnarrative_id: {narrative_id}\napp_id: {app_id}"
        print(f"running job with inputs:\n{inputs}")
        app_id = app_id.lower()
        status = "completed"
        job_error = None
        created_objects = []
        if "fastqc" in app_id:
            job_id = "fastqc_job"
            report_obj = "3/1"
        elif "trimmomatic" in app_id:
            job_id = "trimmomatic_job"
            created_objects = [
                CreatedObject(object_upa=f"{narrative_id}/4/1", object_name="reads_trimmed")
            ]
            report_obj = "5/1"
        elif "spades" in app_id:
            job_id = "spades_job"
            created_objects = [
                CreatedObject(object_upa=f"{narrative_id}/6/1", object_name="reads_trimmed_assembled")
            ]
            report_obj = "7/1"
        elif "quast" in app_id:
            job_id = "quast_job"
            report_obj = "8/1"
        elif "prokka" in app_id:
            job_id = "prokka_job"
            report_obj = "9/1"
            created_objects = [
                CreatedObject(object_name="reads_trimmed_assembled_annotated", object_upa=f"{narrative_id}/10/1")
            ]
        elif "checkm" in app_id:
            job_id = "checkm_job"
            report_obj = "11/1"
        elif "build_genomeset" in app_id:
            job_id = "build_genomeset_job"
            report_obj = None
            created_objects = [
                CreatedObject(object_name="annoted_genomeset", object_upa=f"{narrative_id}/12/1")
            ]
        elif "gtdbtk" in app_id:
            job_id = "gtdbtk_job"
            report_obj = "13/1"
            created_objects = [
                CreatedObject(object_name="genomeset_tree", object_upa=f"{narrative_id}/14/1")
            ]
        return CompletedJob(
            job_id=job_id,
            job_status = status,
            job_error = job_error,
            narrative_id = narrative_id,
            report_upa = f"{narrative_id}/{report_obj}" if report_obj is not None else None,
            created_objects = created_objects
        )

    def build_tasks(
        self, app_name: str, narrative_id: int, input_object_upa: str, app_id: str | None
    ) -> list[Task]:
        get_app_task = Task(
            description=f"Get the app id for the KBase {app_name} app. Return only the app id. This can be found in the catalog.",
            expected_output="An app id with the format module/app, with a single forward-slash",
            agent=self._coordinator.agent,
        )

        # TODO: make sure that input objects are ALWAYS UPAs
        get_app_params_task = Task(
            name=f"1. Get parameters for {app_name}",
            description=f"""
            From the given KBase app id, {app_id}, fetch the list of parameters needed to run it. Use the App and Job manager agent
            for assistance. Using the data object with UPA "{input_object_upa}", populate a dictionary
            with the parameters where the keys are parameter ids, and values are the proper parameter values, or their
            default values if no value can be found or calculated.
            Any input object parameter must be the input object UPA.
            Be sure to make sure there is a non-null value for any parameter that is not optional.
            Any parameter that has a true value for "is_output_object" must have a valid name for the new object.
            The new object name should be based on the input object name, not its UPA. But it must NEVER be identical to the input object name,
            always create a new name.
            If the input object name is not available, the Workspace Manager can assist.
            If the parameter type is 'dropdown', use the allowed 'name' option to determine what should be used, but only set the
            'value' associated with that name, or the default value if any.
            Only alphanumeric characters and underscores are allowed in new object names.
            Return the dictionary of inputs, the app id, and the
            narrative id {narrative_id} for use in the next task. Do not add comments or other text. If the parameters are rejected, examine the reason why and
            reform them. The dictionary of inputs and the app id must not be combined into a single dictionary.
            """,
            expected_output="A dictionary of parameters used to run the app with the given id along with the narrative id.",
            output_pydantic=AppStartInfo,
            agent=self._coordinator.agent,
            context=[get_app_task]
        )

        start_job_task = Task(
            name=f"2. Run app {app_name}",
            description=f"""
            Using the app parameters, app id, and narrative id {narrative_id}, use the `run_job` tool to run a new KBase app. This will run
            the app and return a `CompletedJobAndReport` object that contains the output from the job and a report from the app, if
            applicable.

            - If the job is in an error state, the tool will indicate this in the job_error field.
            - Your job is to call the tool, and return its result directly — do not modify the structure or add commentary.
            - This output will be passed to the next task to interpret the job's report.

            The result must be returned exactly as provided by the tool.
            """,
            expected_output="The CompletedJobAndReport object returned by the monitor_job tool.",
            output_pydantic=CompletedJob,
            agent=self._job.agent,
            context=[get_app_params_task],
        )

        report_retrieval_task = Task(
            name=f"3. Retrieve the report for the finished {app_name} job",
            description="""
                You have received a `CompletedJob` object from the previous task. Use its `report_upa` field to locate the report UPA in the Workspace.

                - If `report_upa` is None, return a string indicating that no report is available due to an error.
                - Otherwise, use the UPA to retrieve the corresponding report object from the Workspace.
                - Return only the **text content** of the report. No JSON, no summary, just the raw report content.

                If no report is found, or the UPA is invalid, return a string indicating so.
            """,

            expected_output="The text of a KBase app report object",
            agent=self._workspace.agent,
            context=[start_job_task]
        )

        report_analysis_task = Task(
            name=f"4. Analyze the report from the {app_name} job",
            description=
            """Analyze the given report and derive some biological insight into the result.
            If the report is not in JSON format, then interpret the document as-is.
            If it is in JSON format, The report may contain content in 3 categories.
            1. "message": this is a brief message describing the outcome of the report
            2. "direct html": this is HTML-formatted information meant to be displayed to the user, and might be a brief summary of the full report.
            3. "html report": this is one or more full HTML-formatted documents containing the report information.

            Regardless of the format, it may be plain text, which can be interpreted as-is. It may also
            also be formatted as HTML. If so, read the HTML document, including any base-64 encoded images for interpretation.

            After interpretation, analyze the report, and summarize the findings with a biological interpretation. Write a brief summary, including
            bullet points when appropriate, formatted in markdown. Your final answer MUST be the summary of the report.

            If there was no report, the report is null, or an empty string, return a note saying that there is no report to analyze.
            If the previous task ended with an error, or another note saying that there is no report to analyze,
            just return a note saying so. Otherwise, return the summary of the report.
            """,
            expected_output="A summary of the report from the previous task",
            agent=self._writer.agent,
            context=[report_retrieval_task]
        )

        save_analysis_task = Task(
            name=f"5. Save the report analysis for {app_name} as markdown",
            description=f"""Save the analysis by adding a markdown cell to the Narrative with id {narrative_id}. The markdown text must
            be the analysis text. If not successful, say so and stop. If an output object was created, ensure that it has both an UPA and name.
            In the end, return the results of the job completion task with both UPA and name for output object. The return result must be normalized to contain
            both the UPA and output object name, if either are present. If the app has neither an output object name or UPA, both of these
            fields may be None.""",
            expected_output="A note with either success or failure of saving the new cell",
            output_pydantic=CompletedJob,
            agent=self._narr.agent,
            extra_content=narrative_id,
            context=[start_job_task, report_analysis_task],
        )

        return [
            get_app_params_task,
            start_job_task,
            report_retrieval_task,
            report_analysis_task,
            save_analysis_task,
        ]
