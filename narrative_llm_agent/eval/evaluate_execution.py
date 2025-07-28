from narrative_llm_agent.workflow_graph.graph_hitl import AnalysisWorkflow, ExecutionWorkflow
from langsmith import Client
import uuid
from narrative_llm_agent.workflow_graph.state import WorkflowState
from openevals.llm import create_llm_as_judge
import json

EXECUTION_EVALUTAION_PROMPT = """You are an expert evaluator assessing multi-agent workflow execution completeness. Your task is to assign a score based on the workflow execution state.

<Rubric>
A complete execution:
- Has 'step_result' field indicating successful completion or job_status = 'completed' with no errors
- Additionally, you can also look at 'completed_steps' field to look at which steps were completed
- Shows error field is None or empty
- Demonstrates successful step completion
- Contains no execution failures or exceptions

When scoring, you should penalize:
- Failed jobs (job_status != 'completed')
- Any non-null values in the error field
- Incomplete step execution
- Workflow termination due to errors
- System failures or exceptions
</Rubric>

<Instructions>
- Examine the step_result and job_status fields for completion status
- Check the error field - any error present indicates failure
- Evaluate completed_steps against workflow progress
- Assess step_result for job completion status
- Score: 1.0 = Complete (no errors), 0.5 = Partially Complete, 0.0 = Not Complete (has errors)
</Instructions>

<Reminder>
The error field is critical - any error value (even if job_status shows completed) should significantly impact the score. Focus on execution success: completed status AND no errors.
Ingnore human feedback, human approval status, and feedback fields for this evaluation.
</Reminder>

<workflow_state>
{outputs}
</workflow_state>

Provide your score (1.0, 0.5, or 0.0) and brief justification based on step_result or job_status and error field.
"""
def make_json_serializable(obj, max_depth=10, current_depth=0):
    """Convert objects to JSON serializable format with improved handling"""
    
    # Prevent infinite recursion
    if current_depth >= max_depth:
        return str(obj)
    
    try:
        # First, try to serialize directly
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        pass
    
    # Handle None
    if obj is None:
        return None
    
    # Handle basic types that should be serializable
    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    # Handle lists and tuples
    if isinstance(obj, (list, tuple)):
        try:
            return [make_json_serializable(item, max_depth, current_depth + 1) for item in obj]
        except Exception:
            return [str(item) for item in obj]
    
    # Handle dictionaries
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            try:
                # Ensure the key is a string
                str_key = str(key)
                result[str_key] = make_json_serializable(value, max_depth, current_depth + 1)
            except Exception as e:
                # If we can't serialize the value, convert to string
                result[str(key)] = str(value)
        return result
    
    # Handle objects with __dict__
    if hasattr(obj, '__dict__'):
        result = {}
        for key, value in obj.__dict__.items():
            try:
                # Skip private attributes and methods
                if key.startswith('_'):
                    continue
                
                str_key = str(key)
                result[str_key] = make_json_serializable(value, max_depth, current_depth + 1)
            except Exception:
                # If we can't serialize the value, convert to string
                result[str(key)] = str(value)
        return result
    
    # Handle other iterables
    try:
        if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
            return [make_json_serializable(item, max_depth, current_depth + 1) for item in obj]
    except Exception:
        pass
    
    # Final fallback - convert to string
    return str(obj)

client = Client()
unique_id = str(uuid.uuid4())[:8]
dataset_name = f"workflow_execution_eval_{unique_id}"
#Create a dataset
dataset = client.create_dataset(
    dataset_name=dataset_name, description="A sample dataset to evaluate execution of the analysis plan for an isolate."
)

sequencing_technology="Illumina sequencing"
organism = "Bacillus subtilis sp. strain UAMC"
genome_type = "isolate"
sample_description = f"""The user has uploaded paired-end sequencing reads into the narrative. Here is the metadata for the reads:
sequencing_technology : {sequencing_technology}
organism: {organism}
genome type : {genome_type}
I want you to generate an analysis plan for annotating the uploaded pair-end reads obtained from {sequencing_technology} for a {genome_type} genome using KBase apps.
The goal is to have a complete annotated genome and classify the microbe. 
"""
initial_state = WorkflowState(
    narrative_id="219917",
    reads_id="219917/2/1",
    description=sample_description,
    steps_to_run=[],
    completed_steps=[],
    last_executed_step={},
    input_object_upa=None,
    last_data_object_upa=None,
    human_approval_status=None,
    human_feedback=None,
    error=None,
    results=None
)
# Create workflow instance
workflow = AnalysisWorkflow(
    analyst_llm="gpt-4.1-cborg", 
    app_flow_llm="gpt-4.1-cborg",
)
narrative_id="219917"
reads_id="219917/2/1"
# Run the planning phase only
workflow_state = workflow.run(
    narrative_id=narrative_id,
    reads_id=reads_id,
    description=sample_description
)
# Create examples
examples = [
    {
        "inputs": {"workflow_state": workflow_state},
        
    },
    {
        "inputs": {"workflow_state": workflow_state},
        
    },
]

client.create_examples(dataset_id=dataset.id, examples=examples)

def wrapped_execution_correctness(inputs: dict, outputs: dict):
    """
    Evaluate the correctness of the execution of the steps in the initial state.
    
    Args:
        inputs (dict): The inputs to evaluate.
    
    Returns:
        dict: A dictionary containing the evaluation results.
    """
   

    correctness_evaluator = create_llm_as_judge(
        prompt=EXECUTION_EVALUTAION_PROMPT,
        choices=[0.0, 0.5, 1.0],
        model="openai:o3-mini",
    )
    eval = correctness_evaluator(inputs=inputs,
                          outputs=outputs,
                          )
    
    return eval

def workflow_execution_target(inputs: dict):
    """Target function that runs your workflow execution"""
    workflow_state = inputs["workflow_state"]
    
    # Your existing execution logic
    execution_workflow = ExecutionWorkflow(
        analyst_llm="gpt-4.1-cborg", 
        validator_llm="gpt-4.1-cborg",
        app_flow_llm="gpt-4.1-cborg",
        writer_llm="gpt-4.1-cborg",
    )
    
    final_state = execution_workflow.run(workflow_state)
    outputs = make_json_serializable(final_state)
    
    return outputs

# Run evaluation
experiment_results = client.evaluate(
    workflow_execution_target,
    data="Execution dataset",  
    evaluators=[
        wrapped_execution_correctness,  
    ],
    experiment_prefix="workflow-execution-eval",
    max_concurrency=2,
)