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
        return "validate_step"  # Proceed to validate the step
def handle_error(state):
    return state.copy(update={
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
