from narrative_llm_agent.agents.analyst_lang import AnalysisSteps
from narrative_llm_agent.agents.kbase_agent import KBaseAgent
from narrative_llm_agent.tools.kgtool_cosine_sim import InformationTool
import os
import json
from langchain.tools import tool
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.util.tool import process_tool_input
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

class DecisionResponse(BaseModel):
    continue_as_planned: bool = Field(
        ...,
        description="Whether to continue with the plan as originally outlined"
    )
    reasoning: str = Field(
        ...,
        description="Explanation for the decision made"
    )
    input_object_upa: str = Field(
        ...,
        description="UPA (Unique Process Address) of the input object for the next step"
    )
    modified_next_steps: list[AnalysisSteps] = Field(
        default_factory=list,
        description="If modifications are needed, include the modified steps here"
    )

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
        self.__init_agent()
    def __init_agent(self: "WorkflowValidatorAgent"):
        @tool("list_objects")
        def list_objects_tool(narrative_id: int) -> str:
            """Fetch a list of objects available in a KBase Narrative. This returns a JSON-formatted
            list of all objects in a narrative. The narrative_id input must be an integer. Do not
            pass in a dictionary or a JSON-formatted string."""
            ws = Workspace(token=self._token)
            return json.dumps(
                ws.list_workspace_objects(
                    process_tool_input(narrative_id, "narrative_id"), as_dict=True
                )
            )
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
        tools = [KGretrieval_tool, list_objects_tool]

        SYSTEM_PROMPT_TEMPLATE = f"""You are {self.role}.
        {self.backstory}
        Your personal goal is: {self.goal}"""
        HUMAN_PROMPT_TEMPLATE = """ Based on the outcome of the last step, evaluate if the next step is still appropriate or needs to be modified.
                Keep in mind that the output object from the last step will be used as input for the next step.
                Consider these factors:
                1. Did the last step complete successfully?
                2. Did it produce the expected output objects if any were expected?
                3. Are there any warnings or errors that suggest we should take a different approach?
                4. Is the next step still scientifically appropriate given the results we've seen?
                """

        prompt = SYSTEM_PROMPT_TEMPLATE + HUMAN_PROMPT_TEMPLATE
        try:
            self.agent = create_react_agent(
                model=self._llm,
                tools=tools,
                prompt=prompt,
                debug = True,
                response_format=DecisionResponse,
            )
        except Exception as e:
            print("Error creating agent:", str(e))
            raise e

