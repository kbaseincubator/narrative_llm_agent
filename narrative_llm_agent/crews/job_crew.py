from narrative_llm_agent.agents.analyst import AnalystAgent
from narrative_llm_agent.agents.job import JobAgent, AppStartInfo, AppOutputInfo
from narrative_llm_agent.agents.narrative import NarrativeAgent
from narrative_llm_agent.agents.workspace import WorkspaceAgent
from narrative_llm_agent.agents.coordinator import CoordinatorAgent
from narrative_llm_agent.agents.metadata import MetadataAgent
from langchain_core.language_models.llms import LLM
from crewai import Crew, Task

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

    def __init__(self, llm: LLM, token: str = None) -> None:
        self._crew_results = []
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

    def start_job(self, app_name: str, input_object_upa: str, narrative_id: int, app_id: str|None=None) -> str:
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
            description=f"""
            From the given KBase app id, {app_id}, fetch the list of parameters needed to run it. Use the App and Job manager agent
            for assistance. Using the data object with UPA "{input_object_upa}", populate a dictionary
            with the parameters where the keys are parameter ids, and values are the proper parameter values, or their
            default values if no value can be found or calculated.
            Any input object parameter must be the input object UPA.
            Be sure to make sure there is a non-null value for any parameter that is not optional.
            Any parameter that has a true value for "is_output_object" must have a valid name for the new object. The new object name should be based on
            the input object name, not its UPA. If the input object name is not available, the Workspace Manager can assist.
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
            description=f"""
            Using the app parameters and app id, use provided tools to start a new KBase app, which will return a job id.
            Use that job id to create a new App Cell in the narrative such that narrative_id={narrative_id}. Return only the
            job id.
            """,
            expected_output="A KBase job id string.",
            agent=self._job.agent,
            context=[get_app_params_task],
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
            output_pydantic=CompletedJob,
            agent=self._job.agent,
            context=[start_job_task],
        )

        # job_completion_task = Task(
        #     description="""Use a tool to fetch the status of KBase job with the given job id.
        #     If it is completed without an error, retrieve the job results.
        #     If the job results contain a reference to a report, with an UPA (a string with format number/number/number),
        #     return it as "report".
        #     If the job results contain a newly created data object, return that as "output_object". This should ideally be an UPA, but might just be
        #     the name of the object. If there are no output objects in the job results, there may have been an output object name set in the app
        #     input parameters. Use that as the result object instead.
        #     If the job results contain an "error" key, return the error.
        #     These results must fit the requested format.
        #     You must always use a tool when interacting with KBase services or databases. If this is delegated, make sure
        #     the delegated agent uses a tool when interacting with KBase.
        #     """,
        #     expected_output="The output of the job including the app id, narrative id, UPA of any output objects, and UPA of a report object. Or an error.",
        #     output_pydantic=CompletedJob,
        #     agent=self._job.agent,
        #     context=[get_app_params_task, start_job_task, monitor_job_task],
        # )

        report_retrieval_task = Task(
            description="""Get the report UPA from the job results (a string with format number/number/number), an
            use a tool to get the report object from the Workspace service. UPAs are unique permanent addresses used to identify data objects.
            The Workspace Manager will be helpful here. Make sure the delegated agent uses a tool for interacting with KBase.
            If there was an error in the job results, return a string saying so and summarizing the error.
            If no report is available, either because there is no report UPA or the report object is unavailable, return a string saying so.
            Otherwise, return the full report text. Your final answer MUST be the report text.
            """,
            expected_output="The text of a KBase app report object",
            agent=self._workspace.agent,
            context=[monitor_job_task]
        )

        report_analysis_task = Task(
            description="""Analyze the report text and derive some insight into the result. Write a brief summary, including bullet points
            when appropriate, formatted in markdown. Your final answer MUST be the summary of the report. If there was no report, the
            report is null or an empty string, return a note saying that there is no report to analyze. If the previous task ended with an error,
            or another note saying that there is no report to analyze, just return a note saying so. Otherwise, return the summary of the report.""",
            expected_output="A summary of the report from the previous task",
            agent=self._coordinator.agent,
            context=[report_retrieval_task]
        )

        save_analysis_task = Task(
            description=f"""Save the analysis by adding a markdown cell to the Narrative with id {narrative_id}. The markdown text must
            be the analysis text. If not successful, say so and stop. If an output object was created, ensure that it has both an UPA and name.
            In the end, return the results of the job completion task with both UPA and name for output object. The return result must be normalized to contain
            both the UPA and output object name, if either are present. If the app has neither an output object name or UPA, both of these
            fields may be None.""",
            expected_output="A note with either success or failure of saving the new cell",
            output_pydantic=CompletedJob,
            agent=self._narr.agent,
            extra_content=narrative_id,
            context=[report_analysis_task, monitor_job_task],
        )

        return [
            # get_app_task,
            get_app_params_task,
            start_job_task,
            make_app_cell_task,
            monitor_job_task,
            # job_completion_task,
            report_retrieval_task,
            report_analysis_task,
            save_analysis_task,
        ]
