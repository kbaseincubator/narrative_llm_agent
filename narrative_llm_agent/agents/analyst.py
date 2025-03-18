from narrative_llm_agent.kbase.service_client import ServerError
from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, Field
from langchain_chroma import Chroma
from langchain.memory import ConversationBufferMemory, ReadOnlySharedMemory
from langchain.chains import RetrievalQA
from langchain.tools import tool
import os
from pathlib import Path
from narrative_llm_agent.kbase.clients.narrative_method_store import (
    NarrativeMethodStore,
)
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import Tool, AgentExecutor, create_tool_calling_agent
from narrative_llm_agent.tools.kgtool_cosine_sim import InformationTool
# from langchain_core.runnables import RunnableConfig
# import chainlit as cl
# from narrative_llm_agent.tools.human_tool import HumanInputChainlit
from narrative_llm_agent.tools.human_tool_not_chainlit import HumanInputRun
from narrative_llm_agent.config import get_config


class AnalystInput(BaseModel):
    query: str = Field(
        description="query to look up KBase documentation, catalog or tutorials"
    )


DEFAULT_CATALOG_DB_DIR: Path = Path(__file__).parent / "Nomic_vector_db_app_catalog"
DEFAULT_DOCS_DB_DIR: Path = Path(__file__).parent / "Nomic_vector_db_kbase_docs"
DEFAULT_TUTORIAL_DB_DIR: Path = Path(__file__).parent / "Nomic_vector_db_app_catalog"



class AnalystAgent(KBaseAgent):
    role = "KBase Analyst and Information Provider"
    goal = "Provide information about KBase, its apps, and its documentation to any who ask."
    backstory = """You are a KBase analyst. You have deep knowledge and experience working with
    KBase tools and applications. You have easy access to the KBase documentation and app catalog knowledge graph. 
    Use kbase_docs_retrieval_tool for designing the analysis plan. Use the KGretrieval tool to get app_id for apps in the analysis plan."""
    _catalog_db_dir: Path
    _docs_db_dir: Path
    _tutorial_db_dir: Path
    _cborg_key: str
    def __init__(
        self: "AnalystAgent",
        llm: LLM,
        token: str = None,
        cborg_api_key: str = None,
        catalog_db_dir: Path | str = None,
        tutorial_db_dir: Path | str = None,
        docs_db_dir: Path | str = None,
    ):
        super().__init__(llm, token=token)
        self._cborg_key = self.__setup_cborg_api_key(cborg_api_key)
        if catalog_db_dir is not None:
            self._catalog_db_dir = Path(catalog_db_dir)
        else:
            self._catalog_db_dir = DEFAULT_CATALOG_DB_DIR

        if docs_db_dir is not None:
            self._docs_db_dir = Path(docs_db_dir)
        else:
            self._docs_db_dir = DEFAULT_DOCS_DB_DIR
        if tutorial_db_dir is not None:
            self._tutorial_db_dir = Path(tutorial_db_dir)
        else:
            self._tutorial_db_dir = DEFAULT_TUTORIAL_DB_DIR

        for db_path in [self._catalog_db_dir, self._docs_db_dir, self._tutorial_db_dir]:
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

    def __setup_cborg_api_key(self, cborg_api_key: str) -> str:
        if cborg_api_key is not None:
            return cborg_api_key
        env_var = get_config().cborg_key_env
        if os.environ.get(env_var):
            return os.environ[env_var]
        raise KeyError("Missing environment variable CBORG API KEY")

    def __init_agent(self: "AnalystAgent") -> None:
        # cfg = RunnableConfig()
        # Check if running with Chainlit
        additional_tools = [HumanInputRun()]
        # if os.getenv("CHAINLIT_RUN"):
        #     cfg["callbacks"] = [cl.LangchainCallbackHandler()]
        #     additional_tools = [HumanInputChainlit()]

        @tool("KBase documentation retrieval tool")
        def kbase_docs_retrieval_tool(query: str):
            """This tool should be used for designing a recommendation plan or analysis workflow. It searches the KBase documentation.
            It is useful for answering questions about how to use KBase applications. 
            It does not contain a list of KBase apps. Do not use it to search for KBase app
            presence. Input should be a fully formed question."""
            return self._create_doc_chain(persist_directory=self._docs_db_dir).invoke(
                {"query": query}
            )
        @tool("KBase tutorial retrieval tool")
        def kbase_tutorial_retrieval_tool(query: str):
            """This has the tutorial narratives. Useful for when you need to answer questions about using the KBase platform, apps, and features for establishing a workflow to acheive a scientific goal. Input should be a fully formed question. Do not use it to search for KBase app
            presence. Input should be a fully formed question."""
            return self._create_doc_chain(persist_directory=self._tutorial_db_dir).invoke(
                {"query": query}
            )

        @tool("KBase app catalog retrieval tool")
        def kbase_app_catalog_retrieval_tool(query: str):
            """Use this tool to search the KBase app catalog. This will provide apps that are available in KBase.
            All apps in the catalog also have a name, app_id, version, tooltip, categories, and description to help you
            to decide which app to use. Input should be a fully formed question."""
            print("running query against the catalog retrieval tool:")
            print(query)
            result = self._create_doc_chain(
                persist_directory=self._catalog_db_dir
            ).invoke({"query": query})
            print("got result")
            print(result)
            return result

        @tool("KBase app validator")
        def kbase_app_validator(app_id: str) -> bool:
            """Use this tool to validate if an app is available in KBase.

            Input should be a single app id with format module_name/app_name."""
            try:
                nms = NarrativeMethodStore()
                nms.get_app_full_info(app_id)
            except ServerError:
                return False
            return True
        @tool("KG retrieval tool")   
        def KGretrieval_tool(input: str):
           """This tool has the KBase app Knowledge Graph. Useful for when you need to confirm the existance of KBase applications and their appid, tooltip, version, category and data objects.
           This tool can also be used for finding total number of apps or which data objects are shared between apps.
           It is also useful for finding accurate app_id for a KBase app.
           The input should always be a KBase app name or data object name and should not include any special characters or version number.
           Do not use this tool if you do not have an app or data object name to search with use the KBase Documentation or Tutorial tools instead
           """
           
           response = self._create_KG_agent().invoke({"input": input})
           #Ensure that the response is properly formatted for the agent to use
           if 'output' in response:
                return response['output']
           return "No response from the tool"
        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            allow_delegation=True,
            llm=self._llm,
            tools=[
                #kbase_app_catalog_retrieval_tool,
                kbase_docs_retrieval_tool,
                kbase_tutorial_retrieval_tool,
                kbase_app_validator,
                KGretrieval_tool
            ]
            + additional_tools,
            memory=True,
        )

    def _create_doc_chain(self, persist_directory: str | Path):
        #If using cborg, use this embedding
        embeddings = OpenAIEmbeddings(openai_api_key=self._cborg_key, 
                                      openai_api_base="https://api.cborg.lbl.gov/v1", model="lbl/nomic-embed-text")
        # Embedding functions to use
        #embeddings = OpenAIEmbeddings(openai_api_key=self._openai_key)
        # Use the persisted database
        vectordb = Chroma(
            persist_directory=str(persist_directory), embedding_function=embeddings
        )
        retriever = vectordb.as_retriever()

        memory = ConversationBufferMemory(memory_key="chat_history")
        readonlymemory = ReadOnlySharedMemory(memory=memory)
        chain_type = "refine"

        # Retrieval chain
        qa_chain = RetrievalQA.from_chain_type(
            llm=self._llm,
            chain_type=chain_type,
            retriever=retriever,
            memory=readonlymemory,
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