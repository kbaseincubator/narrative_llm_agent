from narrative_llm_agent.agents.workspace import WorkspaceAgent
from narrative_llm_agent.agents.coordinator import CoordinatorAgent
from narrative_llm_agent.agents.metadata import MetadataAgent
from crewai import Crew, Task, LLM
from crewai.crews import CrewOutput
from pydantic import BaseModel
from typing import Optional


class InitialDataOutput(BaseModel):
    narrative_id: int
    object_name: str
    object_upa: str

class FetchObjectsList(BaseModel):
    objects: list[InitialDataOutput]

class GenomeReadsMetadata(BaseModel):
    organism: Optional[str]
    read_length: Optional[int]
    insert_size: Optional[int]
    library_type: Optional[str]
    paired_end: Optional[bool]
    platform: Optional[str]
    sequencing_depth: Optional[float]
    genome_size: Optional[int]
    ploidy: Optional[int]
    coverage: Optional[float]
    additional_notes: Optional[dict]
    preferred_assembler: Optional[str]
    preferred_annotator: Optional[str]
    preferred_qc_tools: Optional[list[str]]

class StartupOutput(BaseModel):
    metadata: GenomeReadsMetadata
    narrative_id: int
    object_name: str
    object_upa: str  # UPA of the data object

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
                **results.tasks_output[2].pydantic.model_dump(),
            )
        )
        return self._outputs[-1]

    def build_tasks(self) -> list[Task]:
        startup_objective = """
            Ask the user which narrative id they are using. This will be a number. Return only that number for the next task.
        """

        fetch_objects_objective = """
            Fetch the list of all objects available in the user's narrative. The narrative id is a number available
            in the task context. Do not ask the user for the narrative id. Do not ask the user for the list of data
            objects directly, use a tool. Do not include any objects with type KBaseNarrative.Narrative. Return the name, UPA, and type for each of the objects.
        """

        select_object_objective = """
            From the list of available, ask the user what data they want to assemble and annotate.
            Return the narrative id, the UPA of the user's chosen data object, and the name of the object.
        """

        metadata_objective = """
            Assemble metadata necessary to assemble and annotate the genomic data in the UPA given by context.
            First, retrieve the object metadata for that UPA.
            If there is not enough information here to choose appropriate applications for assembly and annotation,
            then ask the user all necessary questions until enough information is together.
            Note that the user may not know certain information, and this is a valid answer. The user also might not know
            any further information, and this is also a valid answer. Do not keep repeating the requests once the user
            says that they don't have anything else to add.
        """

        store_objective = """
            Use a tool to store the previous conversation in the narrative with the given id. Do not
            ask the user any more questions.
            Format this conversation into markdown text that should resemble an abstract to a biological article.
            Write this text as though you are the scientist - avoid language like "the user prefers...".
            The focus should be on the goals of the work (assembling and annotating genomic reads) and any
            context given previously by the user as to the source and nature of the data. Return the results of the
            conversation.
        """

        startup_task = Task(
            description=startup_objective,
            expected_output="The numeric narrative id. This should be only a number.",
            agent=self._coordinator.agent,
        )

        fetch_reads_task = Task(
            description=fetch_objects_objective,
            expected_output="A list of data objects, each of which has a name, object UPA, and narrative id.",
            output_pydantic=FetchObjectsList,
            context=[startup_task],
            agent=self._workspace.agent
        )

        select_reads_task = Task(
            description=select_object_objective,
            expected_output="Return JSON with narrative_id and reads_object_upa, and reads_object_name keys. reads_object_upa should be an UPA",
            output_pydantic=InitialDataOutput,
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

        store_metadata_task = Task(
            description=store_objective,
            expected_output="Return JSON of the assembled metadata matching the schema. Null values are allowed.",
            output_pydantic=GenomeReadsMetadata,
            agent=self._metadata.agent,
            context=[select_reads_task, metadata_task]
        )

        return [
            startup_task,
            fetch_reads_task,
            select_reads_task,
            metadata_task,
            store_metadata_task
        ]
