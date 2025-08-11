from narrative_llm_agent.config import get_llm
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.tools.narrative_tools import (
    create_markdown_cell,
    get_all_markdown_text,
)
from langgraph.graph.state import StateGraph, CompiledStateGraph, START, END

from langchain_core.prompts import ChatPromptTemplate

from pydantic import BaseModel, ConfigDict


class SummaryWriteupState(BaseModel):
    """
    Includes a Workspace client that can get passed around the nodes,
    to avoid nodes having to deal with auth.
    Though I guess that's implicit with the Workspace...
    """

    narrative_markdown: list[str]
    narrative_id: int
    writeup_doc: str | None = None
    error: str | None = None
    app_list: list[str] = []
    model_config = ConfigDict(arbitrary_types_allowed=True)


writing_system_prompt = """You are a scientific writing assistant tasked with interpreting biological data and
composing clear, accurate summaries. Your writing should reflect scientific precision while remaining accessible
to non-specialist readers. Explain key findings, contextualize results, and highlight biological significance using
well-structured, concise language. Avoid jargon where possible, and define any necessary technical terms. Tailor
tone and detail to a professional yet readable standard, suitable for reports, research summaries, or funding
communications."""

summary_writing_prompt = """
Your task is to cleanup the finalized narrative. This involves the following steps.
1. You are given the text from all narrative markdown cells. These contain the report summaries.
2. Summarize these report summaries together in the context of the provided goals of the narrative project and the apps that were run: {app_list}. There should be one markdown cell for each task, and one at the beginning stating the goals.
3. Format this summary as markdown. It should have the tone of a scientific publication. Write this text as though you are the scientist performing the work - avoid language like "the user performed...". Don't just concatenate the different summaries together, but process and interpret them given the context.

narrative markdown cells:
{narrative_text}
"""


class SummaryWriterGraph:
    """
    Usage:
    Instantiate a WriterGraph object with a narrative id, and optionally a KBase auth token.
    If not, one will be taken from the KB_AUTH_TOKEN environment variable.

    When ready, run run_workflow, which will execute the graph and output the document.

    # TODO: add a reference check that'll automatically grab refs from apps, where applicable
    """

    def __init__(self, ws_client: Workspace, writer_llm: str, writer_token: str = None, token: str = None):
        self._token = token
        self._ws_client = ws_client
        self._writer_llm = writer_llm
        self._writer_token = writer_token
        self._workflow = self._build_graph()

    def run_workflow(self, narrative_id: int, app_list: list[str]):
        initial_state = SummaryWriteupState(
            narrative_markdown=get_all_markdown_text(narrative_id, self._ws_client),
            narrative_id=narrative_id,
            app_list=app_list,
        )
        self._workflow.invoke(initial_state)

    def summary_writer_node(self, state: SummaryWriteupState) -> SummaryWriteupState:
        summary_prompt_template = ChatPromptTemplate(
            [("system", writing_system_prompt), ("user", summary_writing_prompt)]
        )
        llm = get_llm(self._writer_llm, api_key=self._writer_token)
        msg = llm.invoke(
            summary_prompt_template.invoke(
                {"narrative_text": state.narrative_markdown, "app_list": state.app_list}
            )
        )
        return state.model_copy(update={"writeup_doc": msg.content})

    def save_writeup(self, state: SummaryWriteupState) -> SummaryWriteupState:
        create_markdown_cell(state.narrative_id, state.writeup_doc, self._ws_client)
        return state

    def _build_graph(self) -> CompiledStateGraph:
        writer_graph = StateGraph(SummaryWriteupState)
        writer_graph.add_node("writeup", self.summary_writer_node)
        writer_graph.add_node("save_writeup", self.save_writeup)

        writer_graph.add_edge(START, "writeup")
        writer_graph.add_edge("writeup", "save_writeup")
        writer_graph.add_edge("save_writeup", END)

        workflow = writer_graph.compile()
        return workflow
