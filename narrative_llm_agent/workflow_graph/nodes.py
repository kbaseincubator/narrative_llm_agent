from crewai import Crew, Task
from narrative_llm_agent.agents.workflow import WorkflowRunner
from narrative_llm_agent.agents.validator import WorkflowValidatorAgent
from narrative_llm_agent.agents.analyst import AnalystAgent
from narrative_llm_agent.util.json_util import extract_json_from_string, extract_json_from_string_curly
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, TypedDict
from narrative_llm_agent.config import get_llm
import json
import os

# Define a model for each analysis step
class AnalysisStep(BaseModel):
    Step: int
    Name: str
    App: str
    Description: str
    expect_new_object: bool
    app_id: str
    input_data_object: List[str]
    output_data_object: List[str]
# Define a model for the complete workflow
class AnalysisPipeline(BaseModel):
    steps_to_run: List[AnalysisStep]
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
            llm = self.llm_factory("gpt-o1-cborg")
            analyst_expert = AnalystAgent(
                llm=llm, 
                token=self.token, 
                tools_model="o1", 
                provider="cborg"
            )
            
            # Create the analysis task
            analysis_agent_task = Task(
                description=description,
                expected_output="a json of the analysis workflow",
                output_json=AnalysisPipeline,
                agent=analyst_expert.agent
            )
            
            # Create and run the crew
            crew = Crew(
                agents=[analyst_expert.agent],
                tasks=[analysis_agent_task],
                verbose=True,
            )
            
            output = crew.kickoff()
            
            # Extract the JSON from the output
            analysis_plan = extract_json_from_string(output.raw)
            
            # Return updated state with analysis plan
            return state.copy(update={"steps_to_run": analysis_plan, "error": None})
        except Exception as e:
            return state.copy(update={"steps_to_run": None, "error": str(e)})


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
                These steps must be run sequentially. 
                These must be run in the narrative with id {narrative_id} with the input object upa with id {input_object_upa}.
                If any step ends with an error, immediately stop the task and end with an error.
                In the end, return a brief summary of steps taken and resulting output objects.
                """,
                expected_output="A summary of task completion, the number of apps run, and the upa of any output objects.",
                agent=wf_runner.agent
            )
            
            # Create and run the crew
            crew = Crew(
                agents=[wf_runner.agent],
                tasks=[run_apps_task],
                verbose=True,
            )
            print("Running execution crew...")
            result = crew.kickoff()
            
            # Return updated state with results
            return state.copy(update={
                "step_result": result,
                "steps_to_run": remaining_steps,
                "last_executed_step": current_step,
                "error": None
            })
        except Exception as e:
            return state.copy(update={"results": None, "error": str(e)})
    
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
                return state.copy(update={
                    "results": "Workflow complete. All steps were successfully executed.",
                    "error": None
                })
            
            # Initialize the validator agent
            llm = self.llm_factory("gpt-o1-cborg")
            validator = WorkflowValidatorAgent(llm, token=self.token)
            
            # Create the validation task
            validation_task = Task(
                description=f"""
                Analyze the result of the last executed step and determine if the next planned step is appropriate.
                
                Last step executed:
                {json.dumps(last_executed_step)}
                
                Result of the last step:
                {last_step_result}
                
                
                Next planned step:
                {json.dumps(next_step)}
                If this is the first step, i.e. Last step executed is None, then the input object for this step should be paired-end reads object with id {state.reads_id}.
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
                """,
                
                expected_output="A JSON decision on whether to proceed with the next step as planned or modify the workflow.",
                agent=validator.agent,
                output_json=WorkflowDecision,
            )
            
            # Create and run the crew
            crew = Crew(
                agents=[validator.agent],
                tasks=[validation_task],
                verbose=True,
            )
            
            result = crew.kickoff()
            
            # Parse the result to get the decision
            decision_text = result.raw
            # Extract JSON from the result text
            decision_json = extract_json_from_string_curly(decision_text)
            print(f"Decision JSON: {decision_json}")
            if not decision_json:
                # Fallback if JSON extraction fails
                decision_json = {
                    "continue_as_planned": True,
                    "reasoning": "Unable to parse decision, continuing with original plan as a fallback."
                }
            
            # Update the state based on the decision
            if decision_json.get("continue_as_planned", True):
                return state.copy(update={
                    "input_object_upa": decision_json.get("input_object_upa", state.input_object_upa),
                    "validation_reasoning": decision_json.get("reasoning", ""),
                    "error": None
                })
            else:
                # Replace the remaining steps with the modified steps if provided
                modified_steps = decision_json.get("modified_next_steps", [])
                print(f"Modified steps: {modified_steps}")
                return state.copy(update={
                    "steps_to_run": modified_steps if modified_steps else remaining_steps,
                    "input_object_upa": decision_json.get("input_object_upa", state.input_object_upa),
                    "validation_reasoning": decision_json.get("reasoning", ""),
                    "error": None
                })
        except Exception as e:
            return state.copy(update={"error": str(e)})
    
    def handle_error(self, state: WorkflowState):
        """
        Node function for handling errors in the workflow.
        
        Args:
            state (WorkflowState): The current workflow state.
            
        Returns:
            WorkflowState: Updated workflow state with error handling.
        """
        return state.copy(update={
        "results": f"Error: {state.error or 'Unknown error'}"
        })


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
    nodes = WorkflowNodes(token=token, llm_factory=llm_factory)
    return {
        "analyst_node": nodes.analyst_node,
        "workflow_runner_node": nodes.workflow_runner_node,
        "workflow_validator_node": nodes.workflow_validator_node,
        "handle_error": nodes.handle_error
    }