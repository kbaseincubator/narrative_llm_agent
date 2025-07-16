from narrative_llm_agent.workflow_graph.nodes import WorkflowState

# Function to determine the next node based on the state
def next_step_router(state: WorkflowState):
    if state.error:
        return "handle_error"
    if state.steps_to_run:
        return "validate_step"  # Go to validation after running a step
    else:
        return "workflow_end"

def analyst_router(state: WorkflowState):
    if state.error:
        return "handle_error"
    else:
        return "human_approval"  # Go to human approval after analyst

def human_approval_router(state: WorkflowState):
    """Router for human approval node"""
    if state.error:
        return "handle_error"
    elif state.human_approved:
        return "validate_step"  # Proceed to validation if approved
    else:
        return "human_approval"  # Stay in approval state if not approved

def handle_error(state):
    return state.model_copy(update={
        "results": f"Error: {state.error or 'Unknown error'}"
    })

# Router after validation to decide next action
def post_validation_router(state: WorkflowState):
    if state.error:
        return "handle_error"
    if state.steps_to_run:
        return "run_workflow_step"  # Continue with next step
    else:
        return "workflow_end"