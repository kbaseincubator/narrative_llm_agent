from crewai import Crew, Task
from narrative_llm_agent.agents.workflow import WorkflowRunner
from narrative_llm_agent.agents.validator import WorkflowValidatorAgent
from narrative_llm_agent.agents.analyst_lang import AnalystAgent
from narrative_llm_agent.util.json_util import extract_json_from_string, extract_json_from_string_curly
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, TypedDict
from narrative_llm_agent.config import get_llm
import json
import os

# Define a model for each analysis step
class AnalysisStep(BaseModel):
    step: int
    name: str
    app: str
    description: str
    expect_new_object: bool
    app_id: str
    input_data_object: List[str]
    output_data_object: List[str]
# Define a model for the complete workflow
class AnalysisPipeline(BaseModel):
    steps_to_run: List[AnalysisStep]
class WorkflowRunOutput(BaseModel):
    created_object: Optional[str]
    created_object_upa: Optional[str]
    report: Optional[str]
    error: Optional[str]
    report_upa: Optional[str]
    summary: Optional[str]
class WorkflowDecision(BaseModel):
    continue_as_planned: bool
    reasoning: str
    input_object_upa: Optional[str]
    modified_next_steps: List[AnalysisStep] = []
# Define the state schema
class WorkflowState(BaseModel):
    description: str 
    steps_to_run: Optional[List[Dict[str, Any]]] = None
    last_executed_step: Optional[Dict[str, Any]] = None
    narrative_id: int
    reads_id: str
    step_result: Optional[str] = None
    input_object_upa: Optional[str] = None
    error: Optional[str] = None
    results: Optional[str] = None
    last_data_object_upa: Optional[str] = None


class WorkflowNodes:
    """
    Class that encapsulates all node functions used in the workflow graph.
    This class handles creating and managing agents for different steps in the workflow.
    """
    
    def __init__(self, token=None):
        """
        Initialize the WorkflowNodes class.
        
        Args:
            token (str, optional): Authentication token for the KBase API.
                If not provided, will be read from KB_AUTH_TOKEN environment variable.
            llm_factory (callable, optional): Function to create LLM instances.
                If not provided, will use the default get_llm function.
        """
        self.token = token or os.environ.get("KB_AUTH_TOKEN")
        if not self.token:
            raise ValueError("KB_AUTH_TOKEN must be provided either as parameter or environment variable")
        self.llm_factory = get_llm
    
    def analyst_node(self, state: WorkflowState):
        """
        Node function for creating an analysis plan.
        
        Args:
            state (WorkflowState): The current workflow state.
            
        Returns:
            WorkflowState: Updated workflow state with analysis plan.
        """
        try:
            # Get the existing description from the state
            description = state.description
            
            # Initialize the analyst agent
            llm = self.llm_factory("gpt-4.1-mini-cborg")
            analyst_expert = AnalystAgent(
                llm=llm, 
                token=self.token, 
                provider="cborg"
            )
            
            #Create combined description for the agent
            description_complete = description + f"""This analysis is for a Microbiology Resource Announcements (MRA) paper so these need to be a part of analysis. Always keep in mind the following:
                    - The analysis steps should begin with read quality assessment.
                    - Make sure you select appropriate KBase apps based on genome type.
                    - Relevant statistics for the assembly (e.g., number of contigs and N50 values).
                    - Estimates of genome completeness, where applicable.
                    - Classify the microbe for taxonomy, where relevant.

                    Based on the metadata, devise a detailed step-by-step analysis workflow, the apps and app_ids should be from the app graph.
                    The analysis plan should be a json with schema as:

                    {{"Step": "Integer number indicating the step",
                    "Name": "Name of the step", 
                    "Description": "Describe the step",
                    "App": "Name of the app",
                    "expect_new_object": boolean indicating if this step creates a new data object,
                    "app_id": "Id of the KBase app"}}

                    Ensure that app_ids are obtained from the app graph and are correct.
                    Make sure that the analysis plan is included in the final response."""

            output = analyst_expert.agent.invoke({"input":description_complete})
            # Extract the JSON from the output
            analysis_plan = extract_json_from_string(output['output'])
            
            # Return updated state with analysis plan
            return state.model_copy(update={"steps_to_run": analysis_plan, "error": None})
        except Exception as e:
            return state.model_copy(update={"steps_to_run": None, "error": str(e)})


    def workflow_runner_node(self, state: WorkflowState):
        """
        Node function for executing a workflow step.
        
        Args:
            state (WorkflowState): The current workflow state.
            
        Returns:
            WorkflowState: Updated workflow state with execution results.
        """
        try:
            steps_to_run = state.steps_to_run
            narrative_id = state.narrative_id
            reads_id = state.reads_id
            input_object_upa = state.input_object_upa 
            last_data_object_upa = state.last_data_object_upa or input_object_upa

            # Get the current step and remaining steps
            current_step = steps_to_run[0]
            print("current step to run:", current_step)
            remaining_steps = steps_to_run[1:]
            
            # Initialize the workflow runner
            llm = self.llm_factory("gpt-4o-cborg")
            wf_runner = WorkflowRunner(llm)
            
            # Create the task for a single step/app run
            run_apps_task = Task(
                description=f"""
                This task involves running an app, this app is a part of a workflow where the output of one app (if any) is fed into the next as input. 
                Here is the current the task in JSON format: {json.dumps(current_step)}.
                If any task has "expect_new_object" set to True, then that should receive a new data object in its output as a "created_object". That object will be used as input for the next task.
                If a task has "expect_new_object" set to False, then that should not receive a new object to use in the next task. In that case, use the same input object from the previous step for the next one.
                Some apps only produce a report and may not produce an output object.
                The last known data object UPA is: {last_data_object_upa} - this should be used as input if the last step did not produce a data object.
                These steps must be run sequentially. 
                These must be run in the narrative with id {narrative_id} with the input object upa with id {input_object_upa}.
                If any step ends with an error, immediately stop the task and end with an error.
                IMPORTANT: In your response, clearly specify:
                1. Whether a new data object was created
                2. The UPA of any new data objects created (if any)
                3. Any reports or non-data objects generated
                
                In the end, return a brief summary of steps taken and resulting output objects.
                Return your decision as a JSON with this structure:
                ```json
                {{
                    "created_object": "description of the created object",
                    "created_object_upa": "upa of the created object",
                    "report": "brief description of the report",
                    "report_upa": "upa of the report",
                    "error": "any error message",
                    "summary": "summary of the steps taken and resulting output objects",
                }}
                ```
                """,
                expected_output="A JSON object with created_object, created_object_upa, reports, error, output_objects, and summary fields",
                agent=wf_runner.agent,
                output_json=WorkflowRunOutput,  
            )
            
            # Create and run the crew
            crew = Crew(
                agents=[wf_runner.agent],
                tasks=[run_apps_task],
                verbose=True,
            )
            print("Running execution crew...")
            result = crew.kickoff()
            result_json = extract_json_from_string_curly(result.raw)
            if not result_json:
                result_json = {
                    "summary": str(result),
                    "error": None,
                    "created_object_upa": None,
                    "report": None
                }
            new_upa = result_json.get("created_object_upa")
            if new_upa:
                print(f"New UPA from JSON output: {new_upa}")
            # Determine the last data object UPA for the next step
            updated_last_data_object_upa = new_upa if new_upa else last_data_object_upa
            # Return updated state with results
            return state.model_copy(update={
                "step_result": result,
                "steps_to_run": remaining_steps,
                "last_executed_step": current_step,
                "last_data_object_upa": updated_last_data_object_upa,
                "error": result_json.get("error")
            })
        except Exception as e:
            return state.model_copy(update={"results": None, "error": str(e)})
    
    def workflow_validator_node(self, state: WorkflowState):
        """
        Node function for validating workflow results and determining next steps.
        
        Args:
            state (WorkflowState): The current workflow state.
            
        Returns:
            WorkflowState: Updated workflow state with validation results.
        """
        try:
            # Extract the relevant information from the state
            last_step_result = state.step_result or ""
            last_executed_step = state.last_executed_step or {}
            remaining_steps = state.steps_to_run or []
            next_step = remaining_steps[0] if remaining_steps else None
            
            # If there's no next step, we're done
            if next_step is None:
                return state.model_copy(update={
                    "results": "Workflow complete. All steps were successfully executed.",
                    "error": None
                })
            
            # Initialize the validator agent
            llm = self.llm_factory("gpt-4.1-cborg")
            validator = WorkflowValidatorAgent(llm, token=self.token)
            
            # Create the validation task
            
            description=f"""
                Analyze the result of the last executed step and determine if the next planned step is appropriate.
                
                Last step executed:
                {json.dumps(last_executed_step)}
                
                Result of the last step:
                {last_step_result}
                
                AVAILABLE TOOLS:
                - You can use the "kg_retrieval_tool" to find information about KBase apps including their app_id, tooltip, version, category and data objects.
                - You can use the "list_objects" tool to fetch a list of objects available in the narrative with ID {state.narrative_id}. This can help you verify if objects exist or find appropriate objects to use.
            
                If the last step resulted in an error caused by a wrong app id for eg:
                Unable to start the job due to repository `kb_checkm` not being registered. Please contact KBase support for further assistance.'
                Then use the available tools to correct the app id and re-run the last step.
                Next planned step:
                {json.dumps(next_step)}
                IMPORTANT INPUT OBJECT INFORMATION:
                - If this is the first step i.e. last step executed is None, use the paired-end reads object with id {state.reads_id}. Otherwise, the current input object UPA is: {state.input_object_upa}.
                - The last data object UPA (which should be used if the previous step didn't produce a new object) is: {state.last_data_object_upa}
                - The narrative ID is: {state.narrative_id}
                
                IMPORTANT: For the input_object_upa field in your response:
                1. If the previous step created a new data object, use that UPA: {state.input_object_upa}
                2. If the previous step did NOT create a new data object (e.g., it only created a report), use the last valid data object UPA: {state.last_data_object_upa}
                3. If this is the first step, use the paired-end reads object id: {state.reads_id}

                If this is the first step, i.e. Last step executed is None, then the input object for this step should be paired-end reads object with id {state.reads_id}.
                IMPORTANT: For the input_object_upa field, you MUST use the actual UPA from the previous step's output or the {state.reads_id} for the paired-end reads object.
                A valid UPA has the format "workspace_id/object_id/version_id" (like "12345/6/1").UPA fields must be numbers. DO NOT make up UPA values - they must be actual reference IDs extracted from the previous step's output or the initial state.

                Based on the outcome of the last step, evaluate if the next step is still appropriate or needs to be modified.
                Keep in mind that the output object from the last step will be used as input for the next step.
                Consider these factors:
                1. Did the last step complete successfully?
                2. Did it produce the expected output objects if any were expected? 
                3. Are there any warnings or errors that suggest we should take a different approach?
                4. Is the next step still scientifically appropriate given the results we've seen?
                
                Return your decision as a JSON with this structure:
                ```json
                {{
                    "continue_as_planned": true/false,
                    "reasoning": "Your explanation for the decision",
                    "input_object_upa": "upa of the input object for the next step",
                    "modified_next_steps": [] // If modifications are needed, include the modified steps here
                }}
                ```
                """
            
            output = validator.agent.invoke({"input":description})
            
            # Extract JSON from the result text
            decision_json = extract_json_from_string_curly(output['output'])
            print(f"Decision JSON: {decision_json}")
            if not decision_json:
                # Fallback if JSON extraction fails
                decision_json = {
                    "continue_as_planned": True,
                    "reasoning": "Unable to parse decision, continuing with original plan as a fallback."
                }
            
            # Update the state based on the decision
            if decision_json.get("continue_as_planned", True):
                return state.model_copy(update={
                    "input_object_upa": decision_json.get("input_object_upa", state.input_object_upa),
                    "validation_reasoning": decision_json.get("reasoning", ""),
                    "error": None
                })
            else:
                # Replace the remaining steps with the modified steps if provided
                modified_steps = decision_json.get("modified_next_steps", [])
                print(f"Modified steps: {modified_steps}")
                return state.model_copy(update={
                    "steps_to_run": modified_steps if modified_steps else remaining_steps,
                    "input_object_upa": decision_json.get("input_object_upa", state.input_object_upa),
                    "validation_reasoning": decision_json.get("reasoning", ""),
                    "error": None
                })
        except Exception as e:
            return state.model_copy(update={"error": str(e)})
    
    def handle_error(self, state: WorkflowState):
        """
        Node function for handling errors in the workflow.
        
        Args:
            state (WorkflowState): The current workflow state.
            
        Returns:
            WorkflowState: Updated workflow state with error handling.
        """
        return state.model_copy(update={
        "results": f"Error: {state.error or 'Unknown error'}"
        })
    def workflow_end(self,state: WorkflowState):
        return state.model_copy(update={"results": "✅ Workflow complete."})
# functional-style access to the node methods
def create_workflow_nodes(token=None, llm_factory=None):
    """
    Create workflow nodes instance and return node functions.
    For langgraph add node which expects a function to be passed.
    
    Args:
        token (str, optional): Authentication token for the KBase API.
        llm_factory (callable, optional): Function to create LLM instances.
        
    Returns:
        dict: Dictionary containing all node functions.
    """
    nodes = WorkflowNodes(token=token)
    return {
        "analyst_node": nodes.analyst_node,
        "workflow_runner_node": nodes.workflow_runner_node,
        "workflow_validator_node": nodes.workflow_validator_node,
        "handle_error": nodes.handle_error,
        "workflow_end": nodes.workflow_end
    }