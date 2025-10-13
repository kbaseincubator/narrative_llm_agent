import json
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_community.callbacks import get_openai_callback
from pydantic import BaseModel
from narrative_llm_agent.token_counter import TokenCount
from narrative_llm_agent.tools.narrative_tools import create_markdown_cell
from narrative_llm_agent.tools.workspace_tools import get_object_metadata
from narrative_llm_agent.util.tool import process_tool_input
from narrative_llm_agent.kbase.clients.workspace import Workspace
from .kbase_agent import KBaseAgent

INTERACTIVE_SYSTEM_PROMPT = """
You are a Human Interaction Manager and expert project manager for computational biology projects.

Your role: Gather initial information about the genome assembly and annotation pipeline from the user.

Your goal: You are detail-oriented and use experience to gather relevant information about an analysis project.
You are friendly and skilled at interaction with users to make sure that they've provided necessary
information to make sure a project is successful before it begins.

Follow this workflow in order:

1. STARTUP: Ask the user which narrative ID they are using. This will be a number. Once you have it, proceed to the next step.

2. FETCH OBJECTS: Use the list_workspace_objects_tool to fetch all objects available in the user's narrative using the narrative ID.
Do NOT ask the user for the narrative ID again or ask them to list objects directly - use the tool.
Filter out any objects with type "KBaseNarrative.Narrative". Present the name, UPA, and type for each remaining object.

3. SELECT OBJECT: From the list of available objects, ask the user what data they want to assemble and annotate.
Get the narrative ID, UPA of the chosen data object, and the name of the object.

4. GATHER METADATA: For the selected UPA, first use get_object_metadata_tool to retrieve metadata.
If the metadata doesn't provide enough information to choose appropriate applications for assembly and annotation,
ask the user targeted questions about:
- Sequencing machine used
- Project goals and requirements
- Any other relevant technical details
Note: The user may not know certain information - this is valid. Don't keep repeating requests if they say they don't have more information.

5. STORE CONVERSATION: Once you have sufficient information, use store_conversation_tool to save the conversation to the narrative.
Format the conversation as markdown text resembling a biological article abstract.
Write as though you are the scientist (avoid "the user prefers..." language).
Focus on the goals (assembling and annotating genomic reads) and context about data source and nature.
Do NOT ask the user any more questions during this step.

Available tools:
- get_user_input_tool: Use this to ask the user questions and get their responses
- get_object_metadata_tool: To retrieve metadata for KBase objects using UPA
- list_workspace_objects_tool: To list all objects in a workspace using narrative/workspace ID
- store_conversation_tool: To save the conversation summary to a KBase Narrative

Be conversational, ask follow-up questions when needed, but follow the workflow systematically. Always use tools first before asking users for information that tools can provide.
"""

HEADLESS_SYSTEM_PROMPT = """
You are an expert project manager for computational biology projects.

Your role: Gather initial information about the genome assembly and annotation pipeline from the user.

Your goal: You are detail-oriented and use experience to gather relevant information about an analysis project.
You are friendly and skilled at interaction with users to make sure that they've provided necessary
information to make sure a project is successful before it begins.

You must do the following:

1. You will be provided with a narrative ID, a data object ID, a data type, and metadata for the data object.

2. Using this information only, and without asking questions of the user, collate the given information in a
logical manner.

3. Use the store_conversation_tool to save the conversation to the narrative.
Format the conversation as markdown text resembling a biological article abstract.
Write as though you are the scientist (avoid "the user prefers..." language).
Focus on the goals (assembling and annotating genomic reads) and context about data source and nature.

The only available tool you have is the store_conversation_tool, which you must use to store the summary to a KBase Narrative.
"""


class MetadataInput(BaseModel):
    obj_upa: str = "UPA for reads data object"


class UserInputModel(BaseModel):
    prompt: str = "Prompt to show the user for input"


class MetadataAgent(KBaseAgent):
    role: str = "Human Interaction Manager"
    goal: str = "Gather initial information about the genome assembly and annotation pipeline from the user."
    backstory: str = (
        "You are detail-oriented and use experience to gather relevant information about an analysis project. "
        "You are friendly and skilled at interaction with users to make sure that they've provided necessary "
        "information to make sure a project is successful before it begins."
    )
    def __init__(
        self: "MetadataAgent",
        llm: ChatOpenAI,
        token: str = None,
        llm_name: str = "",
        interactive_mode: bool = True
    ) -> None:
        super().__init__(llm, token=token)
        self.current_user_input = None
        self.llm_name = llm_name
        self.__init_agent(interactive_mode)

    def __init_agent(self, interactive_mode: bool) -> None:
        @tool("get-user-input")
        def get_user_input_tool(prompt: str) -> str:
            """Get input from the user by displaying a prompt. Use this tool when you need information from the user."""
            try:
                if self.current_user_input is not None:
                    user_response = self.current_user_input
                    self.current_user_input = None  # Clear after use
                    return f"User responded: {user_response}"
                else:
                    return f"Please provide: {prompt}"
            except Exception as e:
                return f"Error getting user input: {str(e)}"

        @tool("get-object-metadata")
        def get_object_metadata_tool(obj_upa: str) -> str:
            """Return the metadata for a KBase Workspace object with the given UPA."""
            return json.dumps(get_object_metadata(process_tool_input(obj_upa, "obj_upa"), Workspace(token=self._token)))

        @tool("list-objects")
        def list_objects_tool(narrative_id: int) -> str:
            """Fetch a list of objects available in a KBase Narrative."""
            ws = Workspace(token=self._token)
            return json.dumps(
                ws.list_workspace_objects(
                    process_tool_input(narrative_id, "narrative_id"), as_dict=True
                )
            )

        @tool("store-conversation")
        def store_introduction_tool(narrative_id: int, conversation: str) -> str:
            """Store introduction tool. This securely stores the introduction to a Narrative workflow as a
            markdown cell in a KBase Narrative."""
            create_markdown_cell(narrative_id, conversation, Workspace(self._token))
            return f"Successfully stored conversation to narrative {narrative_id}"

        tools = [get_user_input_tool, get_object_metadata_tool, list_objects_tool, store_introduction_tool]

        if interactive_mode:
            system_prompt = INTERACTIVE_SYSTEM_PROMPT
        else:
            system_prompt = HEADLESS_SYSTEM_PROMPT
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder("chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(self._llm, tools, prompt)
        self.agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, stream_runnable=False)

    def invoke(self, llm_input: dict):
        with get_openai_callback() as cb:
            response = self.agent_executor.invoke(llm_input)
            print(f"count: {cb.prompt_tokens} | {cb.completion_tokens}")
            count = TokenCount(prompt_tokens = cb.prompt_tokens, completion_tokens = cb.completion_tokens)
            return response, count
