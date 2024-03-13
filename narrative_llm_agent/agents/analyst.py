from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from langchain_openai import OpenAIEmbeddings
from langchain.pydantic_v1 import BaseModel, Field
from langchain.vectorstores import Chroma
from langchain.memory import ConversationBufferMemory, ReadOnlySharedMemory
from langchain.chains import RetrievalQA
from langchain.tools import tool
import os
from pathlib import Path


class AnalystInput(BaseModel):
    input: str = Field(
        description="query to look up KBase documentation, catalog or tutorials"
    )


class AnalystAgent(KBaseAgent):
    role = "Computational Biologist and Geneticist"
    goal = (
        "Analyze and interpret datasets, and make suggestions into next analysis steps."
    )
    backstory = """You are an expert academic computational biologist with decades of
    experience working in microbial genetics. You have published several genome announcement
    papers and have worked extensively with novel sequence data."""
    _openai_key: str
    _catalog_db_dir: Path = Path(__file__).parent / "vector_db_app_catalog"
    _docs_db_dir: Path = Path(__file__).parent / "vector_db_kbase_docs"

    def __init__(
        self: "AnalystAgent",
        token: str,
        llm: LLM,
        openai_api_key: str = None,
        catalog_db_dir: Path | str = None,
        docs_db_dir: Path | str = None,
    ):
        super().__init__(token, llm)
        self.__setup_openai_api_key(openai_api_key)
        if catalog_db_dir is not None:
            self._catalog_db_dir = Path(catalog_db_dir)
        if docs_db_dir is not None:
            self._docs_db_dir = Path(docs_db_dir)
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
                f"database directory {db_path} not found, unable to make Agent."
            )
        if not db_path.is_dir():
            raise RuntimeError(
                f"database directory {db_path} is not a directory, unable to make Agent."
            )
        db_file = db_path / "chroma.sqlite3"
        if not db_file.exists():
            raise RuntimeError(
                f"Database file {db_file} not found, unable to make Agent."
            )

    def __setup_openai_api_key(self, openai_api_key: str) -> None:
        if openai_api_key is not None:
            self._openai_key = openai_api_key
        elif os.environ.get("OPENAI_API_KEY"):
            self._openai_key = os.environ["OPENAI_API_KEY"]
        else:
            raise KeyError("Missing environment variable OPENAI_API_KEY")

    def __init_agent(self: "AnalystAgent") -> None:
        @tool(
            "Kbase documentation retrieval tool",
            args_schema=AnalystInput,
            return_direct=True,
        )
        def kbase_docs_retrieval_tool(input: str):
            """This tool has the KBase documentation. Useful for when you need to answer questions about how to use Kbase applications. Input should be a fully formed question."""
            persist_directory = "./vector_db_kbase_docs"
            return self._create_doc_chain(persist_directory=persist_directory).invoke(
                {"query": input}
            )

        @tool(
            "Kbase app catalog retrieval tool",
            args_schema=AnalystInput,
            return_direct=True,
        )
        def kbase_appCatalog_retrieval_tool(input: str):
            """This tool has the KBase app catalog. Useful for when you need to find apps available in KBase.
            All apps in the catalog also have name, version tooltip, categories and description to help you to decide which app to use. Input should be a fully formed question."""
            persist_directory = "./vector_db_app_catalog"
            return self._create_doc_chain(persist_directory=persist_directory).invoke(
                {"query": input}
            )

        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            allow_delegation=True,
            llm=self._llm,
            tools=[kbase_appCatalog_retrieval_tool, kbase_docs_retrieval_tool],
        )

    def _create_doc_chain(self, persist_directory):
        # Embedding functions to use
        embeddings = OpenAIEmbeddings(openai_api_key=self._openai_key)
        # Use the persisted database
        vectordb = Chroma(
            persist_directory=persist_directory, embedding_function=embeddings
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
