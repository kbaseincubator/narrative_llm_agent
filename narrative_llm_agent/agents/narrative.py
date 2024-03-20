from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool
from narrative_llm_agent.util.tool import process_tool_input
from narrative_llm_agent.util.narrative import NarrativeUtil
from narrative_llm_agent.kbase.clients.workspace import Workspace

class NarrativeInput(BaseModel):
    narrative_id: int = Field(description="The narrative id. Should be numeric.")

class MarkdownCellInput(BaseModel):
    narrative_id: int = Field(description="The narrative id. Should be numeric.")
    markdown_text: str = Field(description="The markdown text. Must be a string.")

class NarrativeAgent(KBaseAgent):
    role: str = "Narrative Manager"
    goal: str = "Manage construction of a KBase Narrative. Add app and markdown cells, and retrieve cell info to help achieve team goals."
    backstory: str = """You are an expert at the KBase Narrative Interface application with years of experience working with the DoE KBase platform.
    You are responsible for building a Narrative document on behalf of your crew, and otherwise interacting with the KBase Narrative interface.
    You will be creating app cells and importing and formatting text for markdown cells. You will also be fetching cell data, including
    job information and state, for your team. You are an expert at the Jupyter Notebook and notebook cell structure. You have an array of tools
    for your use to help facilitate this role.
    """
    ws_endpoint: str

    def __init__(self: "NarrativeAgent", token: str, llm: LLM) -> "NarrativeAgent":
        super().__init__(token, llm)
        self.__init_agent()
        self.ws_endpoint = self._service_endpoint + "ws"

    def __init_agent(self: "NarrativeAgent"):
        @tool(args_schema=NarrativeInput, return_direct=False)
        def get_narrative(narrative_id: int) -> str:
            """Fetch the Narrative document from the KBase Workspace. This returns the most recent
            version of the Narrative document with the given id as a JSON-formatted string with the
            Narrative document structure. The narrative_id input must be numeric. Do not input a
            dictionary or JSON-formatted string."""
            return self._get_narrative(process_tool_input(narrative_id, "narrative_id"))

        @tool(args_schema=MarkdownCellInput, return_direct=False)
        def add_markdown_cell(narrative_id: int, markdown_text: str) -> str:
            """Add a new markdown cell to an existing Narrative document. This cell gets added to the
            end of the document. The narrative_id must be numeric. The markdown_text must be a string,
            with or without markdown-specific formatting. Do not input a dictionary or JSON-formatted
            string. If successful, this will return a message saying 'success'. If unsuccessful, or if an
            error occurs, an exception will be raised."""
            narrative_id = process_tool_input(narrative_id, "narrative_id")
            markdown_text = process_tool_input(markdown_text, "markdown_text")
            return self._add_markdown_cell(narrative_id, markdown_text)

        self.agent = Agent(
            role = self.role,
            goal = self.goal,
            backstory = self.backstory,
            verbose = True,
            tools = [
                get_narrative,
                # add_app_cell,
                add_markdown_cell
            ],
            llm=self._llm,
            allow_delegation=False,
            memory=True,
        )

    def _get_narrative(self, narrative_id: int) -> str:
        """
        Fetch a Narrative object from the Workspace service with given narrative id.
        This is returned as a JSON string.
        """
        ws = Workspace(self._token, self.ws_endpoint)
        narr_util = NarrativeUtil(ws)
        narr = narr_util.get_narrative_from_wsid(narrative_id)
        return str(narr)

    def _add_markdown_cell(self, narrative_id: int, markdown_text: str) -> str:
        """
        Add a markdown cell to the Narrative object and save it. This inserts the given
        markdown_text into ta new markdown cell. If successful, this returns the string
        'success'.
        """
        ws = Workspace(self._token, self.ws_endpoint)
        narr_util = NarrativeUtil(ws)
        narr = narr_util.get_narrative_from_wsid(narrative_id)
        narr.add_markdown_cell(markdown_text)
        narr_util.save_narrative(narr, narrative_id)
        return "success"
