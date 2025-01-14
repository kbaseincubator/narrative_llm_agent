from narrative_llm_agent.agents.workspace import WorkspaceAgent
from narrative_llm_agent.agents.coordinator import CoordinatorAgent
from narrative_llm_agent.agents.metadata import MetadataAgent
from langchain_core.language_models.llms import LLM
from crewai import Crew, Task
from pydantic import BaseModel


class GenomeAnnotationInput(BaseModel):
    narrative_id: int
    reads_object: str


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
    reads_object: str  # UPA of the reads object


class StartupCrew:
    _token: str
    _llm: LLM

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

    def run_startup(self) -> StartupOutput:
        tasks = self.build_tasks()
        crew = Crew(
            agents=self._agents,
            tasks=tasks,
            verbose=True,
        )
        results = crew.kickoff()
        return StartupOutput(
            metadata=results.tasks_output[2].json_dict,
            **results.tasks_output[1].json_dict,
        )

    def build_tasks(self) -> list[Task]:
        startup_objective = """
            Ask the user which narrative id they are using. This will be a number. Return only that number for the next task.
        """

        get_reads_objective = """
            Use the Workspace Manager to get a list of available reads data objects from the user's narrative.
            Do not ask the user directly, use a tool.
            You will need the UPA for each reads, but should tell the user the names.
            Ask the user with set of reads they want to assemble and annotate. Return the narrative id and the UPA of
            the user's chosen reads object.
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
            expected_output="Return the numeric narrative id. Return only a number.",
            agent=self._coordinator.agent,
        )

        get_reads_task = Task(
            description=get_reads_objective,
            output_json=GenomeAnnotationInput,
            expected_output="Return JSON with narrative_id and reads_object keys. reads_object should be an UPA",
            context=[startup_task],
            agent=self._coordinator.agent,
        )

        metadata_task = Task(
            description=metadata_objective,
            expected_output="Return JSON of the assembled metadata, matching the schema. Null values are allowed.",
            output_json=GenomeReadsMetadata,
            agent=self._metadata.agent,
            context=[get_reads_task],
        )

        return [startup_task, get_reads_task, metadata_task]
