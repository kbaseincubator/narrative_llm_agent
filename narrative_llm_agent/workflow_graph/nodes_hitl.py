import logging
from narrative_llm_agent.crews.job_crew import JobCrew
from narrative_llm_agent.agents.validator import WorkflowValidatorAgent
from narrative_llm_agent.agents.analyst_lang import AnalystAgent
from narrative_llm_agent.kbase.clients.narrative_method_store import NarrativeMethodStore
from narrative_llm_agent.kbase.objects.app_spec import AppSpec
from narrative_llm_agent.tools.job_tools import CompletedJob
from narrative_llm_agent.util.json_util import extract_json_from_string, extract_json_from_string_curly
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from narrative_llm_agent.config import get_llm
import json
import time
import logging

workflow_logger = logging.getLogger("WorkflowExecution")
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

# Define the state schema with human approval fields
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
    # Human approval fields
    human_approval_status: Optional[str] = None  # "approved", "rejected", "cancelled"
    awaiting_approval: bool = False
    human_feedback: Optional[str] = None

class WorkflowNodes:
    """
    Class that encapsulates all node functions used in the workflow graph.
    This class handles creating and managing agents for different steps in the workflow.
    """

    def __init__(self, analyst_llm: str, validator_llm: str, app_flow_llm: str, writer_llm: str, embedding_provider: str, token=None, analyst_token: str | None = None, validator_token: str | None = None, app_flow_token: str | None = None, writer_token: str | None = None, embedding_token: str | None = None):
        """
        Initialize the WorkflowNodes class.

        Args:
            analyst_llm (str): config name for LLM for the analyst
            validator_llm (str): config name for the LLM for the validator
            app_flow_llm (str): config name for the LLM for the app running workflow
            writer_llm (str): config name for the LLM for the summary and report writer
            embedding_provider (str): (one of "cborg" or "nomic"), used for embedding queries to the knowledge graph
            token (str, optional): Authentication token for the KBase API.
        """
        self._analyst_llm = analyst_llm.lower()
        self._validator_llm = validator_llm.lower()
        self._app_flow_llm = app_flow_llm.lower()
        self._writer_llm = writer_llm.lower()
        self._embedding_provider = embedding_provider.lower()
        self._analyst_token = analyst_token
        self._validator_token = validator_token
        self._app_flow_token = app_flow_token
        self._writer_token = writer_token
        self._embedding_token = embedding_token
        self.token = token
        if not self.token:
            raise ValueError("KBase auth token must be provided")

    def analyst_node(self, state: WorkflowState):
        """
        Node function for creating an analysis plan.

        Args:
            state (WorkflowState): The current workflow state.

        Returns:
            WorkflowState: Updated workflow state with analysis plan.
        """
        workflow_logger.info(f"Starting analyst_node for Narrative ID, logging from nodes file: {state.narrative_id}")
        try:
            # Get the existing description from the state
            description = state.description
            workflow_logger.info(f"Descriptio for the analyst agent: {description}")
            # Initialize the analyst agent
            llm = get_llm(self._analyst_llm, api_key=self._analyst_token)
            print(f"Using LLM: {self._analyst_llm} with llm: {llm}")
            analyst_expert = AnalystAgent(
                    llm = llm,
                    provider = self._embedding_provider,
                    api_key=self._analyst_token,
                    token=self.token,
                )
            # Create combined description for the agent
            description_complete = description + """/nThis analysis is for a Microbiology Resource Announcements (MRA) paper so these need to be a part of analysis. Always keep in mind the following:
                    - The analysis steps should begin with read quality assessment.
                    - Make sure you select appropriate KBase apps based on genome type.
                    - Relevant statistics for the assembly (e.g., number of contigs and N50 values).
                    - Estimates of genome completeness, where applicable.
                    - Classify the microbe for taxonomy, where relevant.

                    Based on the metadata, devise a detailed step-by-step analysis workflow, the apps and app_ids should be from the app graph.
                    """
            #config = {"configurable": {"thread_id": "1",}}
            config = {"recursion_limit": 50 }

            output = analyst_expert.agent.invoke({"messages": [{"role": "user", "content": description_complete}]},config)
            # Extract the JSON from the output
            analysis_plan = [step.model_dump() for step in output["structured_response"].steps_to_run]
            workflow_logger.info(f"Analysis plan: {analysis_plan}")
            #Mock analysis plan for testing purposes
            #read from json file
            # file_path = ("/Users/prachigupta/LLM/narrative_agent_test/notebooks/evaluation/mra_isolate.json")
            # with open(file_path, 'r') as file:
            #     workflow_data = json.load(file)
            # analysis_plan = workflow_data.get("steps", [])[:1]
            # print(f"Analysis plan: {analysis_plan}")
            # Return updated state with analysis plan and awaiting approval flag

            analysis_plan = validate_analysis_plan(analysis_plan)

            return state.model_copy(update={
                "steps_to_run": analysis_plan,
                "error": None,
                "awaiting_approval": True
            })
        except Exception as e:
            return state.model_copy(update={"steps_to_run": None, "error": str(e)})

    def human_approval_node(self, state: WorkflowState):
        """
        Node function for human approval of the analysis plan.
        This node checks the approval status and acts accordingly.
        It does NOT block execution - the UI handles the approval flow.

        Args:
            state (WorkflowState): The current workflow state.

        Returns:
            WorkflowState: Updated workflow state based on approval status.
        """
        # Check if we're still awaiting approval
        if state.awaiting_approval and not state.human_approval_status:
            # Still waiting for human input - return state unchanged
            # The UI will handle displaying the approval interface
            return state.model_copy(update={
                "awaiting_approval": True,
                "error": None
            })

        # Handle the different approval statuses
        if state.human_approval_status == "approved":
            print(f"✅ Analysis plan approved for Narrative ID: {state.narrative_id}")
            return state.model_copy(update={
                "awaiting_approval": False,
                "human_feedback": None,
                "error": None
            })

        elif state.human_approval_status == "rejected":
            print(f"❌ Analysis plan rejected for Narrative ID: {state.narrative_id}")
            print(f"Feedback: {state.human_feedback or 'No feedback provided'}")
            return state.model_copy(update={
                "awaiting_approval": False,
                "error": f"Analysis plan rejected. Feedback: {state.human_feedback or 'No feedback provided'}",
                "results": "Analysis plan rejected by user. Please modify parameters and regenerate."
            })

        elif state.human_approval_status == "cancelled":
            print(f"🚫 Analysis workflow cancelled for Narrative ID: {state.narrative_id}")
            return state.model_copy(update={
                "awaiting_approval": False,
                "error": None,
                "results": "Workflow cancelled by user."
            })

        else:
            # Unknown approval status - treat as still awaiting
            return state.model_copy(update={
                "awaiting_approval": True,
                "error": None
            })
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
            step_info = f"Step {i}: {step.get('name', 'Unnamed Step')}\n"
            step_info += f"   App: {step.get('app', 'Unknown App')}\n"
            step_info += f"   App ID: {step.get('app_id', 'Unknown ID')}\n"
            step_info += f"   Description: {step.get('description', 'No description')}\n"
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
                get_llm(self._app_flow_llm, api_key=self._app_flow_token, return_crewai=True),
                get_llm(self._writer_llm, api_key=self._writer_token, return_crewai=True),
                token=self.token
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
                "error": job_result.job_error,
            })
        except Exception as e:
            workflow_logger.info(e)
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
            llm = get_llm(self._validator_llm, api_key=self._validator_token)
            validator = WorkflowValidatorAgent(llm, token=self.token)

            # Create the validation task
            description = f"""
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
                """
            output = validator.agent.invoke({"messages": [{"role": "user", "content": description}]})
            # Extract the JSON from the output
            decision_json =  output['structured_response']
            workflow_logger.info(f"Validator node: {decision_json}")

            # Update the state based on the decision
            if decision_json.continue_as_planned:
                return state.model_copy(update={
                    "input_object_upa": decision_json.input_object_upa or state.input_object_upa,
                    "validation_reasoning": decision_json.reasoning,
                    "error": None
                })
            else:
                # temp until refactor to include structured output
                new_next_steps = decision_json.modified_next_steps
                if len(new_next_steps) == 0:
                    updated_steps = remaining_steps
                if len(new_next_steps) == 1:
                    updated_steps = [new_next_steps[0].dict()] + remaining_steps[1:]
                else:
                    updated_steps = [step.dict() for step in new_next_steps]

                return state.model_copy(update={
                    "steps_to_run": updated_steps,
                    "input_object_upa": decision_json.input_object_upa or state.input_object_upa,
                    "validation_reasoning": decision_json.reasoning,
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
        return state.model_copy(update={
            "results": "✅ Workflow complete."
            })
