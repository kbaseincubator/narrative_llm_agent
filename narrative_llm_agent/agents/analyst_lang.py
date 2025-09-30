from narrative_llm_agent.kbase.service_client import ServerError
from .kbase_agent import KBaseAgent
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_nomic import NomicEmbeddings
from pydantic import BaseModel, Field
from langchain_chroma import Chroma
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain.memory import ConversationBufferMemory, ReadOnlySharedMemory
from langchain.chains import RetrievalQA
from langchain.tools import tool
import os
from pathlib import Path
from narrative_llm_agent.kbase.clients.narrative_method_store import (
    NarrativeMethodStore,
)
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.agents import Tool, AgentExecutor, create_tool_calling_agent
from narrative_llm_agent.tools.kgtool_cosine_sim import InformationTool
from narrative_llm_agent.config import get_config
import traceback
from typing import List

class AnalystInput(BaseModel):
    query: str = Field(
        description="query to look up KBase documentation, catalog or tutorials"
    )
# Model for each step
class AnalysisSteps(BaseModel):
    step: int
    name: str
    app: str
    description: str
    expect_new_object: bool
    app_id: str

# Model for the complete workflow
class AnalysisPlan(BaseModel):
    steps_to_run: List[AnalysisSteps]

DEFAULT_CATALOG_DB_DIR: Path = Path(__file__).parent / "Nomic_vector_db_app_catalog"
DEFAULT_DOCS_DB_DIR: Path = Path(__file__).parent / "Nomic_vector_db_kbase_docs"
DEFAULT_TUTORIAL_DB_DIR: Path = Path(__file__).parent / "Nomic_tutorials_db"



class AnalystAgent(KBaseAgent):
    role = "KBase Analyst and Information Provider"
    goal = "Provide information about KBase, its apps, and its documentation to any who ask."
    backstory = """You are a KBase analyst. You have deep knowledge and experience working with
    KBase tools and applications. You have easy access to the KBase documentation and app catalog knowledge graph.
    Use kbase_docs_retrieval_tool for designing the analysis plan. Use the KGretrieval tool to get app_id for apps in the analysis plan."""
    _catalog_db_dir: Path
    _docs_db_dir: Path
    _tutorial_db_dir: Path
    _api_key: str
    _embeddings: OpenAIEmbeddings | NomicEmbeddings
    def __init__(
        self: "AnalystAgent",
        llm: ChatOpenAI,
        provider: str,
        token: str = None,
        api_key: str = None,
        catalog_db_dir: Path = DEFAULT_CATALOG_DB_DIR,
        tutorial_db_dir: Path = DEFAULT_TUTORIAL_DB_DIR,
        docs_db_dir: Path = DEFAULT_DOCS_DB_DIR,
    ):
        super().__init__(llm, token=token)
        self._api_key = self.__setup_api_key(api_key, provider)
        self._embeddings = self.__setup_embeddings_model(provider)

        self._catalog_db_dir = catalog_db_dir
        self._docs_db_dir = docs_db_dir
        self._tutorials_db_dir = tutorial_db_dir

        for db_path in [self._catalog_db_dir, self._docs_db_dir, self._tutorials_db_dir]:
            self.__check_db_directories(db_path)
        self.__init_agent()


    def __check_db_directories(self, db_path: Path) -> None:
        """
        Checks for presence of the expected database directory. Doesn't look for all files,
        just ensures that the directory is present and it has a `chroma.sqlite3` file.
        If file or directory is missing, this raises a RuntimeError.
        TODO: check for other files if needed
        """
        if not db_path.exists():
            raise RuntimeError(
                f"Database directory {db_path} not found, unable to make Agent."
            )
        if not db_path.is_dir():
            raise RuntimeError(
                f"Database directory {db_path} is not a directory, unable to make Agent."
            )
        db_file = db_path / "chroma.sqlite3"
        if not db_file.exists():
            raise RuntimeError(
                f"Database file {db_file} not found, unable to make Agent."
            )

    def __setup_api_key(self, api_key: str, provider : str) -> str:
        if api_key is not None:
            return api_key
        if provider == "cborg":
            env_var = get_config().cborg_key_env
        else:
            env_var = get_config().openai_key_env
        if os.environ.get(env_var):
            return os.environ[env_var]
        raise KeyError(f"Missing environment variable {provider} API KEY")

    def __setup_embeddings_model(self,provider: str) -> OpenAIEmbeddings | NomicEmbeddings:
        """
        Sets up the llm for the tools
        """
        if provider == "cborg":
            # If using cborg, use this embedding
            return OpenAIEmbeddings(
                openai_api_key=self._api_key,
                openai_api_base="https://api.cborg.lbl.gov",
                model="lbl/nomic-embed-text",
                check_embedding_ctx_length=False
            )
        else:
            # If using openai, Embedding functions to use
            return NomicEmbeddings(
                nomic_api_key=os.environ.get("NOMIC_API_KEY"),
                model="nomic-embed-text-v1.5",
                dimensionality=768
            )

    def __init_agent(self: "AnalystAgent") -> None:

        @tool("kbase_doc_tool")
        def kbase_docs_retrieval_tool(query: str):
            """This tool should be used for designing a recommendation plan or analysis workflow. It searches the KBase documentation.
            It is useful for answering questions about how to use KBase applications.
            It does not contain a list of KBase apps. Do not use it to search for KBase app
            presence. Input should be a fully formed question."""
            print(self._docs_db_dir)
            return self._create_doc_chain(persist_directory=self._docs_db_dir).invoke(
                {"query": query}
            )
        @tool("kbase_tutorial_tool")
        def kbase_tutorial_retrieval_tool(query: str):
            """This has the tutorial narratives. Useful for when you need to answer questions about using the KBase platform, apps, and features for establishing a workflow to acheive a scientific goal. Input should be a fully formed question. Do not use it to search for KBase app
            presence. Input should be a fully formed question."""
            return self._create_doc_chain(persist_directory=self._tutorial_db_dir).invoke(
                {"query": query}
            )

        @tool("kbase_app_catalog_tool")
        def kbase_app_catalog_retrieval_tool(query: str):
            """Use this tool to search the KBase app catalog. This will provide apps that are available in KBase.
            All apps in the catalog also have a name, app_id, version, tooltip, categories, and description to help you
            to decide which app to use. Input should be a fully formed question."""

            result = self._create_doc_chain(
                persist_directory=self._catalog_db_dir
            ).invoke({"query": query})

            return result

        @tool("kbase_app_validator_tool")
        def kbase_app_validator(app_id: str) -> bool:
            """Use this tool to validate if an app is available in KBase.

            Input should be a single app id with format module_name/app_name."""
            try:
                nms = NarrativeMethodStore()
                nms.get_app_full_info(app_id)
            except ServerError:
                return False
            return True
        @tool("kg_retrieval_tool")
        def KGretrieval_tool(input: str):
            """This tool has the KBase app Knowledge Graph. Useful for when you need to confirm the existance of KBase applications and their appid, tooltip, version, category and data objects.
            This tool can also be used for finding total number of apps or which data objects are shared between apps.
            It is also useful for finding accurate app_id for a KBase app.
            The input should always be a KBase app name or data object name and should not include any special characters or version number.
            Do not use this tool if you do not have an app or data object name to search with use the KBase Documentation or Tutorial tools instead
            """
            try:
                # Call get_information directly
                get_information = InformationTool(uri=os.environ.get('NEO4J_URI'), user=os.environ.get('NEO4J_USERNAME'), password=os.environ.get('NEO4J_PASSWORD'))
                result = get_information.run({'entity':input, 'entity_type':'AppCatalog'})
                return result
            except Exception as e:
                return f"Error querying Knowledge Graph: {str(e)}"
        # @tool("kg_retrieval_tool")
        # def KGretrieval_tool(input: str):
        #    """This tool has the KBase app Knowledge Graph. Useful for when you need to confirm the existance of KBase applications and their appid, tooltip, version, category and data objects.
        #    This tool can also be used for finding total number of apps or which data objects are shared between apps.
        #    It is also useful for finding accurate app_id for a KBase app.
        #    The input should always be a KBase app name or data object name and should not include any special characters or version number.
        #    Do not use this tool if you do not have an app or data object name to search with use the KBase Documentation or Tutorial tools instead
        #    """

        #    response = self._create_KG_agent().invoke({"input": input})
        #    #Ensure that the response is properly formatted for the agent to use
        #    if 'output' in response:
        #         return response['output']
        #    return "No response from the tool"

        tools = [
            kbase_docs_retrieval_tool,
            kbase_tutorial_retrieval_tool,
            KGretrieval_tool,
        ]

        SYSTEM_PROMPT_TEMPLATE = f"""You are {self.role}.
        {self.backstory}
        Your personal goal is: {self.goal}"""

        HUMAN_PROMPT_TEMPLATE = """
        Answer the following questions accurately and concisely.
        You have access tools.

        Use the following format:

        Question: the input question you must answer

        Thought: you should always think about what to do

        Action: the action to take, should be one of tools

        Action Input: the input to the action

        Observation: the result of the action

        ... (this Thought/Action/Action Input/Observation can repeat N times)

        Thought: I now know the final answer

        Final Answer: the final answer to the original input question.
        Always follow these:
        -Stop after you arrive at the Final Answer.
        -When suggesting apps to user for performing analysis make sure to review the associated meta data and select analysis steps or apps accordingly. 
        If it is an isolates genome, make sure to select apps that are suitable for this genome type. If its metagenome, select apps that are suitable for metagenomes.
        -When generating detailed multi step analysis plans, be precise suggesting one app per step.
        -Always use the KBase Documentation tool to find relevant KBase apps then check the Knowledge Graph to find the full app name, appid, tooltip, version, category and data objects.
        -Do not use the Knowledge Graph tool if you do not have an app or data object name to search with use the KBase Documentation or Tutorial tools instead.

        Thought:{agent_scratchpad}
        """
        # prompt = ChatPromptTemplate.from_messages([
        #     SystemMessagePromptTemplate.from_template(
        #         template=SYSTEM_PROMPT_TEMPLATE
        #     ),
        #     MessagesPlaceholder(variable_name='react_chat_history', optional=True),
        #     HumanMessagePromptTemplate.from_template(
        #         input_variables=["tools", "input", "react_chat_history", "agent_scratchpad"],
        #         template=HUMAN_PROMPT_TEMPLATE
        #     )
        # ])
        prompt = SYSTEM_PROMPT_TEMPLATE + HUMAN_PROMPT_TEMPLATE
        try:
            self.agent = create_react_agent(
                model=self._llm,
                tools=tools,
                prompt=prompt,
                debug=True,
                response_format=AnalysisPlan,
            )
            print("Created the agent successfully")

            # self.agent = AgentExecutor(
            #     agent=agent,
            #     tools=tools,
            #     verbose=True,
            #     memory=ConversationBufferMemory(memory_key="react_chat_history", return_messages=True),
            #     handle_parsing_errors=True
            # )
        except Exception as e:
            print("Error creating the agent:")
            traceback.print_exc()
            raise e

    def _create_doc_chain(self, persist_directory: str | Path):
        """Create a retrieval qa chain for the given embeddings model and persist directory."""
        # Use the persisted database
        vectordb = Chroma(
            persist_directory=str(persist_directory),
            embedding_function=self._embeddings
        )
        retriever = vectordb.as_retriever()
        chain_type = "refine"

        # Retrieval chain
        qa_chain = RetrievalQA.from_chain_type(
            llm=self._llm,
            chain_type=chain_type,
            retriever=retriever,
        )

        return qa_chain

    def _create_KG_agent(self):

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful tool that finds information about KBase applications in the Knowledge Graph "
                    "Use the tools provided to you to find KBase apps and related properties."
                    "Do only the things the user specifically requested. ",
                ),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        tools=[InformationTool(uri=os.environ.get('NEO4J_URI'), user=os.environ.get('NEO4J_USERNAME'), password=os.environ.get('NEO4J_PASSWORD'))]
        agent = create_tool_calling_agent(self._llm, tools, prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        return agent_executor
