from narrative_llm_agent.agents.workspace import WorkspaceAgent
from narrative_llm_agent.agents.coordinator import CoordinatorAgent
from narrative_llm_agent.agents.metadata import MetadataAgent
from langchain_core.language_models.llms import LLM
from crewai import Crew, Task
from crewai.crews import CrewOutput
from pydantic import BaseModel


class InitialReadsOutput(BaseModel):
    narrative_id: int
    reads_object_name: str
    reads_object_upa: str

class FetchReadsList(BaseModel):
    reads: list[InitialReadsOutput]

class GenomeReadsMetadata(BaseModel):
    organism: str | None
    read_length: int | None
    insert_size: int | None
    library_type: str | None
    paired_end: bool | None
    platform: str | None
    sequencing_depth: float | None
    genome_size: int | None
    ploidy: int | None
    coverage: float | None
    additional_notes: dict | None
    preferred_assembler: str | None
    preferred_annotator: str | None
    preferred_qc_tools: list[str] | None


class StartupOutput(BaseModel):
    metadata: GenomeReadsMetadata
    narrative_id: int
    reads_object_name: str
    reads_object_upa: str  # UPA of the reads object


class StartupCrew:
    _token: str
    _llm: LLM
    _outputs: list[StartupOutput]
    _crew_results: list[CrewOutput]

    def __init__(self, llm: LLM, token: str = None) -> None:
        self._token = token
        self._llm = llm
        self._workspace = WorkspaceAgent(llm, token=token)
        self._coordinator = CoordinatorAgent(llm)
        self._metadata = MetadataAgent(llm, token=token)
        self._agents = [
            self._workspace.agent,
            self._coordinator.agent,
            self._metadata.agent,
        ]
        self._crew_results = []
        self._outputs = []


    def run_startup(self) -> StartupOutput:
        tasks = self.build_tasks()
        crew = Crew(
            agents=self._agents,
            tasks=tasks,
            verbose=True,
        )
        results = crew.kickoff()
        self._crew_results.append(results)

        self._outputs.append(
            StartupOutput(
                metadata=results.tasks_output[3].pydantic,
                **results.tasks_output[2].pydantic.dict(),
            )
        )
        return self._outputs[-1]

    def build_tasks(self) -> list[Task]:
        startup_objective = """
            Ask the user which narrative id they are using. This will be a number. Return only that number for the next task.
        """

        fetch_reads_objective = """
            Fetch the list of all reads objects available in the user's narrative. The narrative id is a number available
            in teh task context. Do not ask the user for the narrative id. Do not ask the user for the list of reads
            directly, use a tool. Return the UPA and name for each of the reads objects.
        """

        select_reads_objective = """
            From the list of available reads, ask the user with set of reads they want to assemble and annotate.
            Return the narrative id, the UPA of the user's chosen reads object, and the name of the reads object.
        """

        metadata_objective = """
            Assemble metadata necessary to assemble and annotate the genomic reads in the UPA given by context.
            First, retrieve the object metadata for that UPA.
            If there is not enough information here to choose appropriate applications for assembly and annotation, then ask the user all necessary questions until enough information is together.
            Note that the user may not know certain information, and this is a valid answer.
            Assemble the final results into a JSON string and store this conversation in the from the context.
            Return the final results.
        """

        startup_task = Task(
            description=startup_objective,
            expected_output="The numeric narrative id. This should be only a number.",
            agent=self._coordinator.agent,
        )

        fetch_reads_task = Task(
            description=fetch_reads_objective,
            expected_output="A list of reads objects, each of which has a name, object UPA, and narrative id.",
            output_pydantic=FetchReadsList,
            context=[startup_task],
            agent=self._workspace.agent
        )

        select_reads_task = Task(
            description=select_reads_objective,
            expected_output="Return JSON with narrative_id and reads_object_upa, and reads_object_name keys. reads_object_upa should be an UPA",
            output_pydantic=InitialReadsOutput,
            context=[startup_task, fetch_reads_task],
            agent=self._coordinator.agent,
        )

        metadata_task = Task(
            description=metadata_objective,
            expected_output="Return JSON of the assembled metadata, matching the schema. Null values are allowed.",
            output_pydantic=GenomeReadsMetadata,
            agent=self._metadata.agent,
            context=[select_reads_task],
        )

        return [
            startup_task,
            fetch_reads_task,
            select_reads_task,
            metadata_task
        ]
