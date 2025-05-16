from narrative_llm_agent.agents.kbase_agent import KBaseAgent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import Tool, AgentExecutor, create_tool_calling_agent
from narrative_llm_agent.tools.kgtool_cosine_sim import InformationTool
import os
from langchain.tools import tool
class WorkflowValidatorAgent(KBaseAgent):
    role: str = "You are a workflow validator, responsible for analyzing app run results and determining next steps."
    goal: str = "Ensure that each step in a computational biology workflow produces expected results and that subsequent steps are appropriate."
    backstory: str = """You are an experienced computational biologist with deep expertise in KBase workflows. 
    You analyze results from each step and determine if the workflow should continue as planned or be modified based on input/output data objects for the apps.
    You also look for any errors in the workflow and suggest fixes. You have tools to help you find KBase apps and their properties like app_id, tooltip, version, category and data objects.
    """
    
    def __init__(self: "WorkflowValidatorAgent", llm, token: str = None):
        self._llm = llm
        self._token = token
        @tool("kg_retrieval_tool")
        def KGretrieval_tool(input: str):
           """This tool has the KBase app Knowledge Graph. Useful for when you need to confirm the existance of KBase applications and their appid, tooltip, version, category and data objects.
           It is also useful for finding accurate app_id for a KBase app.
           The input should always be a KBase app name or data object name and should not include any special characters or version number.
           Do not use this tool if you do not have an app or data object name to search with use the KBase Documentation or Tutorial tools instead
           """

           response = self._create_KG_agent().invoke({"input": input})
           #Ensure that the response is properly formatted for the agent to use
           if 'output' in response:
                return response['output']
           return "No response from the tool"
        prompt = ChatPromptTemplate.from_messages(
        [
            ("system", f"{self.backstory}"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
        )
        tools = [KGretrieval_tool]
        agent = create_tool_calling_agent(
            llm=self._llm,
            tools=tools,
            prompt=prompt,
            )
        
        self.agent = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,)
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