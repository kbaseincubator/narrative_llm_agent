from narrative_llm_agent.crews.job_crew import JobCrew
from narrative_llm_agent.agents.validator import WorkflowValidatorAgent
from narrative_llm_agent.agents.analyst_lang import AnalystAgent
from narrative_llm_agent.tools.job_tools import CompletedJob
from narrative_llm_agent.util.json_util import extract_json_from_string, extract_json_from_string_curly
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from narrative_llm_agent.config import get_llm
import json
import os
import time
from langgraph.types import interrupt, Command
import datetime

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
    steps_to_run: List[Dict[str, Any]] = None
    last_executed_step: Dict[str, Any]
    completed_steps: List[Dict[str, Any]]
    narrative_id: int
    reads_id: str
    step_result: Optional[CompletedJob] = None
    input_object_upa: Optional[str] = None
    error: Optional[str] = None
    results: Optional[str] = None
    last_data_object_upa: Optional[str] = None
    human_approval_status: Optional[str] = None  # "approved", "rejected", "cancelled", "pending"
    human_feedback: Optional[str] = None  # Human feedback for revisions

class WorkflowNodes:
    """
    Class that encapsulates all node functions used in the workflow graph.
    This class handles creating and managing agents for different steps in the workflow.
    """

    def __init__(self, analyst_llm: str, validator_llm: str, app_flow_llm: str, writer_llm: str, embedding_provider: str, token=None, approval_handler=None):
        """
        Initialize the WorkflowNodes class.

        Args:
            analyst_llm (str): config name for LLM for the analyst
            validator_llm (str): config name for the LLM for the validator
            app_flow_llm (str): config name for the LLM for the app running workflow
            writer_llm (str): config name for the LLM for the summary and report writer
            embedding_provider (str): (one of "cborg" or "nomic"), used for embedding queries to the knowledge graph
            token (str, optional): Authentication token for the KBase API.
                If not provided, will be read from KB_AUTH_TOKEN environment variable.
            approval_handler (optional): Handler for human approval (for Streamlit integration)
        """
        self._analyst_llm = analyst_llm.lower()
        self._validator_llm = validator_llm.lower()
        self._app_flow_llm = app_flow_llm.lower()
        self._writer_llm = writer_llm.lower()
        self._embedding_provider = embedding_provider.lower()
        self.token = token or os.environ.get("KB_AUTH_TOKEN")
        self.approval_handler = approval_handler
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
            llm = self.llm_factory(self._analyst_llm)

            analyst_expert = AnalystAgent(
                llm,
                self._embedding_provider,
                token=self.token,
            )

            #Create combined description for the agent
            description_complete = description + f"""\nThis analysis is for a Microbiology Resource Announcements (MRA) paper so these need to be a part of analysis. Always keep in mind the following:
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

            # If we have human feedback, include it in the description for revision
            if state.human_feedback:
                description_complete += f"\n\nHuman feedback to incorporate: {state.human_feedback}"
                description_complete += "\nPlease revise the analysis plan based on the feedback provided."

            output = analyst_expert.agent.invoke({"input":description_complete})
            # Extract the JSON from the output
            analysis_plan = extract_json_from_string(output["output"])

            # Return updated state with analysis plan
            return state.model_copy(update={
                "steps_to_run": analysis_plan, 
                "error": None,
                "human_approval_status": None,  # Reset approval status for new plan
                "human_feedback": None  # Clear feedback after incorporating it
            })
        except Exception as e:
            return state.model_copy(update={"steps_to_run": None, "error": str(e)})

    def human_approval_node(self, state: WorkflowState):
        """
        Node function for getting human approval of the analysis plan.
        This supports both Streamlit and command-line interfaces.

        Args:
            state (WorkflowState): The current workflow state.

        Returns:
            WorkflowState: Updated workflow state with human approval status.
        """
        # Format the analysis plan for human review
        plan_summary = self._format_analysis_plan(state.steps_to_run)
         # Log for debugging
        print("\n" + "="*80)
        print("🔍 ANALYSIS PLAN REVIEW")
        print("="*80)
        print(f"Narrative ID: {state.narrative_id}")
        print(f"Reads ID: {state.reads_id}")
        print(f"Description: {state.description}")
        print("\n📋 PROPOSED ANALYSIS STEPS:")
        print("-"*50)
        print(plan_summary)
        print("\n" + "="*80)
        print("⏸️  Workflow paused - waiting for UI approval...")
        # Prepare approval request data for the UI
        approval_data = {
            "analysis_plan": state.steps_to_run,
            "plan_summary": plan_summary,
            "narrative_id": state.narrative_id,
            "reads_id": state.reads_id,
            "description": state.description,
        }
        
        # Notify the UI handler if available
        if self.approval_handler:
            self.approval_handler.set_approval_request(approval_data)
        
        # Use LangGraph interrupt to pause and wait for UI response
        user_input = interrupt({
            "type": "human_approval",
            "message": "Waiting for human approval of analysis plan",
            "data": approval_data
        })
        
        # Process the structured response from the UI
        if user_input.get("approved"):
            return Command(
                update={
                    "human_approval_status": "approved",
                    "human_feedback": None,
                    "error": None
                },
                goto="validate_step"
            )
        
        elif user_input.get("rejected"):
            feedback =  "Please revise the analysis plan."
            return Command(
                update={
                    "human_approval_status": "rejected",
                    "human_feedback": feedback,
                    "error": None
                },
                goto="analyst"
            )
        
        elif user_input.get("cancelled"):
            return Command(
                update={
                    "human_approval_status": "cancelled",
                    "human_feedback": None,
                    "error": None,
                    "results": "Workflow cancelled by user."
                },
                goto="workflow_end"  # or your end node name
            )
        
        else:
            # Handle unexpected input - could retry or error out
            return Command(
                update={
                    "human_approval_status": "error",
                    "error": "Invalid approval response received",
                },
                goto="handle_error"  # or retry the approval
            )
    def _command_line_human_approval(self, state: WorkflowState):
        """
        Handle human approval through command line interface.
        """
        # Format the analysis plan for human review
        plan_summary = self._format_analysis_plan(state.steps_to_run)
        
        print("\n" + "="*80)
        print("🔍 ANALYSIS PLAN REVIEW")
        print("="*80)
        print(f"Narrative ID: {state.narrative_id}")
        print(f"Reads ID: {state.reads_id}")
        print(f"Description: {state.description}")
        print("\n📋 PROPOSED ANALYSIS STEPS:")
        print("-"*50)
        print(plan_summary)
        print("\n" + "="*80)
        
        # Get human input
        
        user_input = input("\nDo you approve this analysis plan?\n"
                            "Enter 'approve' (or 'a') to proceed\n"
                            "Enter 'reject' (or 'r') to request revisions\n"
                            "Enter 'cancel' (or 'c') to cancel the workflow\n"
                            "Your choice: ").strip().lower()
        
        if user_input in ['approve', 'a']:
            return state.model_copy(update={
                "human_approval_status": "approved",
                "human_feedback": None,
                "error": None
            })
        
        elif user_input in ['reject', 'r']:
            feedback = input("\nPlease provide feedback for revisions: ").strip()
            return state.model_copy(update={
                "human_approval_status": "rejected",
                "human_feedback":  "Please revise the analysis plan.",
                "error": None
            })
        
        elif user_input in ['cancel', 'c']:
            return state.model_copy(update={
                "human_approval_status": "cancelled",
                "human_feedback": None,
                "error": None,
                "results": "Workflow cancelled by user."
            })
        
        else:
            print("❌ Invalid input. Please enter 'approve', 'reject', or 'cancel' (or use 'a', 'r', 'c')")

    def _format_analysis_plan(self, steps: List[Dict[str, Any]]) -> str:
        """
        Format the analysis plan for human-readable display.
        
        Args:
            steps: List of analysis steps
            
        Returns:
            Formatted string representation of the analysis plan
        """
        if not steps:
            return "No steps defined in the analysis plan."
        
        formatted_steps = []
        for i, step in enumerate(steps, 1):
            step_info = f"Step {i}: {step.get('Name', 'Unnamed Step')}\n"
            step_info += f"   App: {step.get('App', 'Unknown App')}\n"
            step_info += f"   App ID: {step.get('app_id', 'Unknown ID')}\n"
            step_info += f"   Description: {step.get('Description', 'No description')}\n"
            step_info += f"   Creates new object: {'Yes' if step.get('expect_new_object', False) else 'No'}\n"
            formatted_steps.append(step_info)
        
        return "\n".join(formatted_steps)

    def app_runner_node(self, state: WorkflowState) -> WorkflowState:
        """
        Node function for running an app in a single step.

        Args:
            state (WorkflowState): The current workflow state.

        Returns:
            WorkflowState: Updated workflow state with execution results.
        """
        steps_to_run = state.steps_to_run
        current_step = steps_to_run[0]
        remaining_steps = steps_to_run[1:]

        app_id = current_step["app_id"]
        input_object_upa = state.input_object_upa
        try:
            jc = JobCrew(
                self.llm_factory(self._app_flow_llm, return_crewai=True),
                self.llm_factory(self._writer_llm, return_crewai=True)
            )
            result = jc.start_job(app_id, input_object_upa, state.narrative_id, app_id=app_id)
            job_result: CompletedJob = result.pydantic
            updated_last_data_object_upa = state.last_data_object_upa
            if len(job_result.created_objects):
                updated_last_data_object_upa = job_result.created_objects[0].object_upa
            return state.model_copy(update={
                "step_result": job_result,
                "steps_to_run": remaining_steps,
                "last_executed_step": current_step,
                "completed_steps": state.completed_steps + [current_step],
                "last_data_object_upa": updated_last_data_object_upa,
                "error": job_result.job_error
            })
        except Exception as e:
            print(e)
            return state.model_copy(update={
                "results": None,
                "step_result": None,
                "error": str(e)
            })

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
            llm = self.llm_factory(self._validator_llm)
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

            output = validator.agent.invoke({"input": description})

            # Extract JSON from the result text
            decision_json = extract_json_from_string_curly(output['output'])
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
                # temp until refactor to include structured output
                new_next_steps = decision_json.get("modified_next_steps", [])
                if len(new_next_steps) == 0:
                    updated_steps = remaining_steps
                if len(new_next_steps) == 1:
                    updated_steps = [new_next_steps[0]] + remaining_steps[1:]
                else:
                    updated_steps = new_next_steps

                return state.model_copy(update={
                    "steps_to_run": updated_steps,
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

    def workflow_end(self, state: WorkflowState):
        return state.model_copy(update={"results": "✅ Workflow complete."})

# functional-style access to the node methods
def create_workflow_nodes(analyst_llm: str, validator_llm: str, app_flow_llm: str, writer_llm: str, embedding_provider: str, token: str=None, approval_handler=None):
    """
    Create workflow nodes instance and return node functions.
    For langgraph add node which expects a function to be passed.

    Args:
        analyst_llm (str): config name for LLM for the analyst
        validator_llm (str): config name for the LLM for the validator
        app_flow_llm (str): config name for the LLM for the app running workflow
        writer_llm (str): config name for the LLM for the summary and report writer
        embedding_provider (str): embedding provider
        token (str, optional): Authentication token for the KBase API.
        approval_handler (optional): Handler for human approval (for Streamlit integration)

    Returns:
        dict: Dictionary containing all node functions.
    """
    nodes = WorkflowNodes(analyst_llm, validator_llm, app_flow_llm, writer_llm, embedding_provider, token=token, approval_handler=approval_handler)
    return {
        "analyst_node": nodes.analyst_node,
        "human_approval_node": nodes.human_approval_node,
        "app_runner_node": nodes.app_runner_node,
        "workflow_validator_node": nodes.workflow_validator_node,
        "handle_error": nodes.handle_error,
        "workflow_end": nodes.workflow_end
    }