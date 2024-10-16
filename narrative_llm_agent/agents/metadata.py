from typing import Type, Callable
from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from pydantic import BaseModel, Field
from narrative_llm_agent.util.tool import process_tool_input
from narrative_llm_agent.util.narrative import NarrativeUtil
from narrative_llm_agent.kbase.clients.workspace import Workspace
from crewai_tools import tool, BaseTool
import json

class MetadataInput(BaseModel):
    obj_upa: str = "UPA for reads data object"

class StoreConversationInput(BaseModel):
    narrative_id: int = Field(..., description="id of the Narrative to store the conversation in")
    json_conversation: str = Field(..., description="JSON format of the conversation to store")

class StoreConversationTool(BaseTool):
    name: str = "Conversation storage tool"
    description: str = "Securely store the results of a conversation in a KBase Narrative."
    args_schema: Type[BaseModel] = StoreConversationInput
    storage_fn: Callable

    def _run(self, **kwargs) -> str:
        narrative_id = kwargs.get("narrative_id")
        json_conversation = kwargs.get("json_conversation", "no conversation supplied")
        print("this is the JSON:\n----------\n")
        print(json.loads(json_conversation))
        print(f"stored in narrative {narrative_id}")
        print("-------------")
        self.storage_fn(narrative_id, json_conversation)

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

    def __init__(self: "MetadataAgent", token: str, llm: LLM, initial_prompts=None) -> None:
        super().__init__(token, llm)
        if initial_prompts is None:
            initial_prompts = []
        self.initial_prompts = initial_prompts
        self.__init_agent()

    def __init_agent(self) -> None:
        @tool("User Conversation Tool")
        def conversation_tool(argument: str) -> str:
            """Converse with the user until all questions are fully answered."""
            print(argument)
            return input()

        @tool("Get object metadata")
        def get_object_metadata(obj_upa: str) -> str:
            """Return the metadata for a KBase Workspace object with the given UPA."""
            return self._get_object_metadata(process_tool_input(obj_upa, "obj_upa"))

        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            tools = [conversation_tool, get_object_metadata, StoreConversationTool(storage_fn=self._store_conversation)],
            llm=self._llm,
            allow_delegation=False,
            memory=True,
        )

    def _get_object_metadata(self: "MetadataAgent", obj_upa: str) -> str:
        """Gets object metadata from a KBase UPA string and returns it as JSON."""
        # look up object info first, get metadata from that to form a prompt.
        # then have the agent converse with the user.
        print("looking up obj info for " + obj_upa)
        ws = Workspace(self._token, endpoint=self._service_endpoint + "ws")
        obj_info = ws.get_object_info(obj_upa)
        print("got object info")
        print(obj_info)
        return json.dumps(obj_info["metadata"])

    def _store_conversation(self: "MetadataAgent", narrative_id: int, json_conversation: str) -> str:
        """Stores JSON-formatted results of a conversation in a Narrative markdown cell."""
        ws = Workspace(self._token, endpoint=self._service_endpoint + "ws")
        narr_util = NarrativeUtil(ws)
        narr = narr_util.get_narrative_from_wsid(narrative_id)
        narr.add_markdown_cell(json_conversation)
        narr_util.save_narrative(narr, narrative_id)
        return "Conversation successfully stored."
