from narrative_llm_agent.kbase.service_client import ServerError
from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, Field
from langchain_chroma import Chroma
from langchain.memory import ConversationBufferMemory, ReadOnlySharedMemory
from langchain.chains import RetrievalQA
from crewai_tools import tool
import os
from pathlib import Path
from narrative_llm_agent.kbase.clients.narrative_method_store import NarrativeMethodStore
# from langchain_core.runnables import RunnableConfig
# import chainlit as cl
# from narrative_llm_agent.tools.human_tool import HumanInputChainlit
from narrative_llm_agent.config import get_config

class AnalystInput(BaseModel):
    query: str = Field(
        description="query to look up KBase documentation, catalog or tutorials"
    )


DEFAULT_CATALOG_DB_DIR: Path = Path(__file__).parent / "vector_db_app_catalog"
DEFAULT_DOCS_DB_DIR: Path = Path(__file__).parent / "vector_db_kbase_docs"


class AnalystAgent(KBaseAgent):
    role = "KBase Analyst and Information Provider"
    goal = "Provide information about KBase, its apps, and its documentation to any who ask."
    backstory = """You are a KBase analyst. You have deep knowledge and experience working with
    KBase tools and applications. You have easy access to the KBase documentation and app catalog."""
    # role = "Computational Biologist and Geneticist"
    # goal = (
    #     "Analyze and interpret datasets, and make suggestions into next analysis steps."
    # )
    # backstory = """You are an expert academic computational biologist with decades of
    # experience working in microbial genetics. You have published several genome announcement
    # papers and have worked extensively with novel sequence data. You are an experienced expert
    # at data analysis and interpretation. You have a talent for delegating data retrieval and
    # job running tasks to your coworkers. You don't do much of the work of data generation,
    # but are very good at coordinating tasks among your coworkers, managing their process,
    # and extracting knowledge from the results."""
    _openai_key: str
    _catalog_db_dir: Path
    _docs_db_dir: Path

    def __init__(
        self: "AnalystAgent",
        llm: LLM,
        token: str = None,
        openai_api_key: str = None,
        catalog_db_dir: Path | str = None,
        docs_db_dir: Path | str = None,
    ):
        super().__init__(llm, token=token)
        self._openai_key = self.__setup_openai_api_key(openai_api_key)

        if catalog_db_dir is not None:
            self._catalog_db_dir = Path(catalog_db_dir)
        else:
            self._catalog_db_dir = DEFAULT_CATALOG_DB_DIR

        if docs_db_dir is not None:
            self._docs_db_dir = Path(docs_db_dir)
        else:
            self._docs_db_dir = DEFAULT_DOCS_DB_DIR

        for db_path in [self._catalog_db_dir, self._docs_db_dir]:
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

    def __setup_openai_api_key(self, openai_api_key: str) -> str:
        if openai_api_key is not None:
            return openai_api_key
        env_var = get_config().openai_key_env
        if os.environ.get(env_var):
            return os.environ[env_var]
        raise KeyError("Missing environment variable OPENAI_API_KEY")

    def __init_agent(self: "AnalystAgent") -> None:
        # cfg = RunnableConfig()
        # Check if running with Chainlit
        additional_tools = []
        # if os.getenv("CHAINLIT_RUN"):
        #     cfg["callbacks"] = [cl.LangchainCallbackHandler()]
        #     additional_tools = [HumanInputChainlit()]

        @tool("KBase documentation retrieval tool")
        def kbase_docs_retrieval_tool(query: str):
            """This tool searches the KBase documentation. It is useful for answering questions about how to use
            KBase applications. It does not contain a list of KBase apps. Do not use it to search for KBase app
            presence. Input should be a fully formed question."""
            return self._create_doc_chain(persist_directory=self._docs_db_dir).invoke(
                {"query": query}
            )

        @tool("KBase app catalog retrieval tool")
        def kbase_app_catalog_retrieval_tool(query: str):
            """Use this tool to search the KBase app catalog. This will provide apps that are available in KBase.
            All apps in the catalog also have a name, version, tooltip, categories, and description to help you
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


        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            allow_delegation=True,
            llm=self._llm,
            tools=[kbase_app_catalog_retrieval_tool, kbase_docs_retrieval_tool, kbase_app_validator]
            + additional_tools,
            memory=True,
        )

    def _create_doc_chain(self, persist_directory: str | Path):
        # Embedding functions to use
        embeddings = OpenAIEmbeddings(openai_api_key=self._openai_key)
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
