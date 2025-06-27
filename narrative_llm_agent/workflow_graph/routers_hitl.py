from narrative_llm_agent.workflow_graph.nodes_hitl import WorkflowState

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
        return "human_approval"  # Route to human approval after analyst creates plan

def human_approval_router(state: WorkflowState):
    """
    Router to handle human approval decisions.
    
    Args:
        state (WorkflowState): The current workflow state
        
    Returns:
        str: The next node to execute based on approval status
    """
    if state.error:
        return "handle_error"
    
    approval_status = state.human_approval_status
    
    if approval_status == "approved":
        return "validate_step"  # Proceed to validation if approved
    elif approval_status == "rejected":
        return "analyst"  # Go back to analyst for revision if rejected
    elif approval_status == "cancelled":
        return "workflow_end"  # End workflow if cancelled
    else:
        # This shouldn't happen, but handle as error if approval status is unknown
        return "handle_error"

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