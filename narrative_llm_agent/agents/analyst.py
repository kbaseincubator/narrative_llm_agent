from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from langchain_openai import OpenAIEmbeddings
from langchain.pydantic_v1 import BaseModel, Field
from langchain.vectorstores import Chroma
from langchain.memory import ConversationBufferMemory, ReadOnlySharedMemory
from langchain.chains import LLMChain, RetrievalQA
from langchain.agents import initialize_agent, Tool, AgentExecutor, ZeroShotAgent
from langchain.tools import BaseTool, tool


class AnalystInput(BaseModel):
    input: str = Field(description="query to look up KBase documentation, catalog or tutorials")

class AnalystAgent(KBaseAgent):
    role="Computational Biologist and Geneticist"
    goal="Analyze and interpret datasets, and make suggestions into next analysis steps."
    backstory="""You are an expert academic computational biologist with decades of
    experience working in microbial genetics. You have published several genome announcement
    papers and have worked extensively with novel sequence data."""

    def __init__(self: "AnalystAgent", token: str, llm: LLM):
        super().__init__(token, llm)
        self.__init_agent()

    def __init_agent(self: "AnalystAgent"):

        @tool("Kbase documentation retrieval tool", args_schema = AnalystInput, return_direct=True)
        def kbase_docs_retrieval_tool(input: str):
            """This tool has the KBase documentation. Useful for when you need to answer questions about how to use Kbase applications. Input should be a fully formed question. """
            persist_directory = "./vector_db_kbase_docs"
            return self._create_doc_chain(persist_directory=persist_directory).invoke({"query": input})
            
        @tool("Kbase app catalog retrieval tool", args_schema = AnalystInput, return_direct=True)
        def kbase_appCatalog_retrieval_tool(input: str):
            """This tool has the KBase app catalog. Useful for when you need to find apps available in KBase. 
            All apps in the catalog also have name, version tooltip, categories and description to help you to decide which app to use. Input should be a fully formed question. """
            persist_directory = "./vector_db_app_catalog"
            return self._create_doc_chain(persist_directory=persist_directory).invoke({"query": input})
            
        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            allow_delegation=True,
            llm=self._llm,
            tools=[kbase_appCatalog_retrieval_tool, kbase_docs_retrieval_tool]
        )

    def _create_doc_chain(self, persist_directory):
            # Embedding functions to use
            embeddings = OpenAIEmbeddings(openai_api_key=self._token)
            # Use the persisted database
            vectordb = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
            retriever = vectordb.as_retriever()


            memory = ConversationBufferMemory(memory_key="chat_history")
            readonlymemory = ReadOnlySharedMemory(memory=memory)
            chain_type = 'refine'
            
            # Retrieval chain 
            qa_chain = RetrievalQA.from_chain_type(llm=self._llm, chain_type=chain_type, retriever=retriever,memory=readonlymemory)
            
            return qa_chain
        