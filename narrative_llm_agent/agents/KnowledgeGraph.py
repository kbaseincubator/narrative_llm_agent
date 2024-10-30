from .kbase_agent import KBaseAgent
from crewai import Agent
from langchain_core.language_models.llms import LLM
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import tool
from narrative_llm_agent.tools.information_tool import InformationTool
from langchain.tools.render import format_tool_to_openai_function
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.agents import AgentExecutor
from langchain.agents import load_tools
import os
from langchain_core.runnables import RunnableConfig
import chainlit as cl

# from langchain_community.tools import HumanInputRun
from narrative_llm_agent.tools.human_tool import HumanInputChainlit


class KGInput(BaseModel):
    input: str = Field(description="query to look up KBase Knowledge Graph")


class KGAgent(KBaseAgent):
    role = "Knowledge Graph retrieval"
    goal = "Use the knowledge graph to find the latest and updated information about the KBase apps."
    backstory = """You are an expert in utilizing the Knowledge Graph tools available to you to answer questions related to the KBase Knowledge Graph """
    _openai_key: str

    def __init__(
        self: "KGAgent", llm: LLM, token: str = None, openai_api_key: str = None
    ):
        super().__init__(llm, token=token)
        self.__setup_openai_api_key(openai_api_key)
        self.__init_agent()

    def __setup_openai_api_key(self, openai_api_key: str) -> None:
        if openai_api_key is not None:
            self._openai_key = openai_api_key
        elif os.environ.get("OPENAI_API_KEY"):
            self._openai_key = os.environ["OPENAI_API_KEY"]
        else:
            raise KeyError("Missing environment variable OPENAI_API_KEY")

    def __init_agent(self: "KGAgent") -> None:
        cfg = RunnableConfig()
        # Check if running with Chainlit
        if os.getenv("CHAINLIT_RUN"):
            cfg["callbacks"] = [cl.LangchainCallbackHandler()]
            human_tools = [HumanInputChainlit()]
        else:
            human_tools = load_tools(["human"])

        @tool("KG retrieval tool", args_schema=KGInput, return_direct=True)
        def KGretrieval_tool(input: str):
            """This tool has the KBase app Knowledge Graph. Useful for when you need to find the KBase applications and their tooltip, version, category and data objects.
            The input should always be a KBase app name and should not include any special characters or version number."""
            return self._create_KG_agent().invoke({"input": input})["output"]

        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            allow_delegation=True,
            llm=self._llm,
            tools=[KGretrieval_tool] + human_tools,
            memory=True,
        )

    def _create_KG_agent(self):
        tools = [InformationTool()]

        llm_with_tools = self._llm.bind(
            functions=[format_tool_to_openai_function(t) for t in tools]
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful tool that finds information about KBase applications in the Knowledge Graph "
                    " and recommends them. Use the tools provided to you to find KBase apps and related properties.  If tools require follow up questions, "
                    "make sure to ask the user for clarification. Make sure to include any "
                    "available options that need to be clarified in the follow up questions "
                    "Do only the things the user specifically requested. ",
                ),
                MessagesPlaceholder(variable_name="chat_history"),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        agent = (
            {
                "input": lambda x: x["input"],
                "chat_history": lambda x: _format_chat_history(x["chat_history"])
                if x.get("chat_history")
                else [],
                "agent_scratchpad": lambda x: format_to_openai_function_messages(
                    x["intermediate_steps"]
                ),
            }
            | prompt
            | llm_with_tools
            | OpenAIFunctionsAgentOutputParser()
        )
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        return agent_executor
