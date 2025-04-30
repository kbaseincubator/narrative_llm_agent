from narrative_llm_agent.tools.narrative_tools import create_markdown_cell
from narrative_llm_agent.tools.workspace_tools import get_object_metadata
from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from pydantic import BaseModel
from narrative_llm_agent.util.tool import process_tool_input
from narrative_llm_agent.kbase.clients.workspace import Workspace
from crewai.tools import tool
import json


class MetadataInput(BaseModel):
    obj_upa: str = "UPA for reads data object"

class MetadataAgent(KBaseAgent):
    initial_prompts = [
        "What narrative id?",
        "What reads object name?",
        "What machine was used to get reads?",
    ]

    role: str = "Human Interaction Manager"
    goal: str = "Gather initial information about the genome assembly and annotation pipeline from the user."
    backstory: str = (
        "You are an expert project manager and computational biologist. "
        "You are detail-oriented and use experience to gather relevant information about an analysis project. "
        "You are friendly and skilled at interaction with users to make sure that they've provided necessary "
        "information to make sure a project is successful before it begins."
    )

    def __init__(
        self: "MetadataAgent",
        llm: LLM,
        token: str = None,
        initial_prompts: list[str] = None,
    ) -> None:
        super().__init__(llm, token=token)
        if initial_prompts is None:
            initial_prompts = []
        self.initial_prompts = initial_prompts
        self.__init_agent()

    def __init_agent(self) -> None:
        @tool("conversation-tool")
        def conversation_tool(argument: str) -> str:
            """Converse with the user until all questions are fully answered."""
            print(argument)
            return input()

        @tool("get-object-metadata")
        def get_object_metadata_tool(obj_upa: str) -> str:
            """Return the metadata for a KBase Workspace object with the given UPA."""
            return json.dumps(get_object_metadata(process_tool_input(obj_upa, "obj_upa"), Workspace(token=self._token)))

        @tool("store-conversation")
        def store_introduction_tool(narrative_id: int, conversation: str) -> str:
            """Store introduction tool. This securely stores the introduction to a Narrative workflow as a
            markdown cell in a KBase Narrative."""
            create_markdown_cell(narrative_id, conversation, Workspace(self._token))

        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            tools=[
                conversation_tool,
                get_object_metadata_tool,
                store_introduction_tool,
            ],
            llm=self._llm,
            allow_delegation=False,
            memory=True,
        )

