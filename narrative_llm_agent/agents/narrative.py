from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from pydantic import BaseModel, Field
from langchain.tools import tool
from narrative_llm_agent.util.tool import process_tool_input
from narrative_llm_agent.util.narrative import NarrativeUtil
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine
from narrative_llm_agent.kbase.clients.narrative_method_store import (
    NarrativeMethodStore,
)
from narrative_llm_agent.kbase.objects.narrative import Narrative


class NarrativeInput(BaseModel):
    narrative_id: int = Field(description="The narrative id. Should be numeric.")


class MarkdownCellInput(BaseModel):
    narrative_id: int = Field(description="The narrative id. Should be numeric.")
    markdown_text: str = Field(description="The markdown text. Must be a string.")


class AppCellFromJobInput(BaseModel):
    narrative_id: int = Field(description="The narrative id. Should be numeric.")
    job_id: str = Field(
        description="The unique identifier for a job running in the KBase Execution Engine. This must be a 24 character hexadecimal string. This must not be a dictionary or JSON-formatted string."
    )


class NarrativeAgent(KBaseAgent):
    role: str = "Narrative Manager"
    goal: str = "Manage construction of a KBase Narrative. Add app and markdown cells, and retrieve cell info to help achieve team goals."
    backstory: str = """You are an expert at the KBase Narrative Interface application with years of experience working with the DoE KBase platform.
    You are responsible for building a Narrative document on behalf of your crew, and otherwise interacting with the KBase Narrative interface.
    You will be creating app cells and importing and formatting text for markdown cells. You will also be fetching cell data, including
    job information and state, for your team. You are an expert at the Jupyter Notebook and notebook cell structure. You have an array of tools
    for your use to help facilitate this role.
    """

    def __init__(
        self: "NarrativeAgent", llm: LLM, token: str = None
    ) -> "NarrativeAgent":
        super().__init__(llm, token=token)
        self.__init_agent()

    def __init_agent(self: "NarrativeAgent"):
        @tool("get-narrative-document", args_schema=NarrativeInput, return_direct=False)
        def get_narrative(narrative_id: int) -> str:
            """Fetch the Narrative document from the KBase Workspace. This returns the most recent
            version of the Narrative document with the given id as a JSON-formatted string with the
            Narrative document structure. The narrative_id input must be numeric. Do not input a
            dictionary or JSON-formatted string."""
            return self._get_narrative(process_tool_input(narrative_id, "narrative_id"))

        @tool("get-narrative-state", args_schema=NarrativeInput, return_direct=False)
        def get_narrative_state(narrative_id: int) -> str:
            """Get the current state of a Narrative from the KBase workspace. This returns the most
            recent version of the Narrative document with the given id in a reduced format that can be
            more easily interpreted by an LLM with less confusion. The narrative_id input must be
            numeric. Do not input a dictionary or JSON-formatted string."""
            return self._get_narrative_state(
                process_tool_input(narrative_id, "narrative_id")
            )

        @tool("add-markdown-cell", args_schema=MarkdownCellInput, return_direct=False)
        def add_markdown_cell(narrative_id: int, markdown_text: str) -> str:
            """Add a new markdown cell to an existing Narrative document. This cell gets added to the
            end of the document. The narrative_id must be numeric. The markdown_text must be a string,
            with or without markdown-specific formatting. Do not input a dictionary or JSON-formatted
            string. If successful, this will return a message saying 'success'. If unsuccessful, or if an
            error occurs, an exception will be raised."""
            narrative_id = process_tool_input(narrative_id, "narrative_id")
            markdown_text = process_tool_input(markdown_text, "markdown_text")
            return self._add_markdown_cell(narrative_id, markdown_text)

        @tool("add-app-cell", args_schema=AppCellFromJobInput, return_direct=False)
        def add_app_cell(narrative_id: int, job_id: str) -> str:
            """Add a new app cell to the bottom of an existing Narrative document. This app cell can be
            used to track the state and status of a running job. The narrative_id must be numeric. The
            job_id must be a string representing a KBase job. Do not input a dictionary or JSON-formatted
            string. If successful, this will return a message saying 'success'. If unsuccessful, or if an
            error occurs, an exception will be raised."""
            narrative_id = process_tool_input(narrative_id, "narrative_id")
            job_id = process_tool_input(job_id, "job_id")
            return self._add_app_cell(narrative_id, job_id)

        @tool("get-all-markdown-cells", return_direct=False)
        def get_all_narrative_markdown_cells(narrative_id: int) -> list[str]:
            """
            Get the text content of all markdown cells in the Narrative, as Markdown, in order.
            """
            narrative_id = process_tool_input(narrative_id, "narrative_id")
            return self._get_all_markdown_text(narrative_id)

        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            tools=[
                get_narrative,
                add_app_cell,
                add_markdown_cell,
                get_narrative_state,
                get_all_narrative_markdown_cells
            ],
            llm=self._llm,
            allow_delegation=False,
            memory=True,
        )

    def _get_narrative(
        self, narrative_id: int, as_json: bool = True
    ) -> str | Narrative:
        """
        Fetch a Narrative object from the Workspace service with given narrative id.
        This is returned as a JSON string.
        """
        ws = Workspace(token=self._token)
        narr_util = NarrativeUtil(ws)
        narr = narr_util.get_narrative_from_wsid(narrative_id)
        if as_json:
            return str(narr)
        return narr

    def _get_narrative_state(self, narrative_id: int) -> str:
        narr = self._get_narrative(narrative_id, as_json=False)
        ee = ExecutionEngine(token=self._token)
        return narr.get_current_state(ee)

    def _add_markdown_cell(self, narrative_id: int, markdown_text: str) -> str:
        """
        Add a markdown cell to the Narrative object and save it. This inserts the given
        markdown_text into ta new markdown cell. If successful, this returns the string
        'success'.
        """
        ws = Workspace(token=self._token)
        narr_util = NarrativeUtil(ws)
        narr = narr_util.get_narrative_from_wsid(narrative_id)
        narr.add_markdown_cell(markdown_text)
        narr_util.save_narrative(narr, narrative_id)
        return "success"

    def _add_app_cell(self, narrative_id: int, job_id: str) -> str:
        """
        Add an app cell to the Narrative object and save it. This uses the job id to look
        up all the app information required to rebuild an app cell. It adds the cell to the
        bottom of the narrative in the state it was in during the last check. If successful,
        this returns the string 'success'.
        """
        ws = Workspace(token=self._token)
        ee = ExecutionEngine(token=self._token)
        nms = NarrativeMethodStore()
        job_state = ee.check_job(job_id)
        app_spec = nms.get_app_spec(job_state.job_input.app_id)

        narr_util = NarrativeUtil(ws)
        narr = narr_util.get_narrative_from_wsid(narrative_id)
        narr.add_app_cell(job_state, app_spec)
        narr_util.save_narrative(narr, narrative_id)
        return "success"

    def _get_all_markdown_text(self, narrative_id: int) -> list[str]:
        narr_util = NarrativeUtil(Workspace())
        narr = narr_util.get_narrative_from_wsid(narrative_id)
        md_cells = narr.get_markdown()
        return [cell.source for cell in md_cells]
