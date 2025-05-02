import pytest
from narrative_llm_agent.workflow_graph.routers import (
    next_step_router,
    analyst_router,
    handle_error,
    post_validation_router
)
from narrative_llm_agent.workflow_graph.nodes import WorkflowState

@pytest.fixture
def base_state():
    """Create a basic WorkflowState for testing."""
    return WorkflowState(
        description="Test workflow",
        narrative_id=123,
        reads_id="test_reads"
    )

def test_next_step_router_with_error(base_state):
    """Test next_step_router when state has an error."""
    state = base_state.model_copy(update={"error": "Test error"})
    result = next_step_router(state)
    assert result == "handle_error"

def test_next_step_router_with_steps(base_state):
    """Test next_step_router when state has steps remaining."""
    state = base_state.model_copy(update={
        "steps_to_run": [{"Step": 1, "Name": "Test Step"}]
    })
    result = next_step_router(state)
    assert result == "validate_step"

def test_next_step_router_no_steps(base_state):
    """Test next_step_router when state has no steps remaining."""
    state = base_state.model_copy(update={"steps_to_run": []})
    result = next_step_router(state)
    assert result == "workflow_end"

def test_analyst_router_with_error(base_state):
    """Test analyst_router when state has an error."""
    state = base_state.model_copy(update={"error": "Analysis error"})
    result = analyst_router(state)
    assert result == "handle_error"

def test_analyst_router_no_error(base_state):
    """Test analyst_router when state has no error."""
    result = analyst_router(base_state)
    assert result == "validate_step"

def test_handle_error(base_state):
    """Test handle_error function."""
    state = base_state.model_copy(update={"error": "Test error"})
    result = handle_error(state)
    assert result.results == "Error: Test error"

def test_handle_error_no_error_message(base_state):
    """Test handle_error function with no specific error message."""
    result = handle_error(base_state)
    assert result.results == "Error: Unknown error"

def test_post_validation_router_with_error(base_state):
    """Test post_validation_router when state has an error."""
    state = base_state.model_copy(update={"error": "Validation error"})
    result = post_validation_router(state)
    assert result == "handle_error"

def test_post_validation_router_with_steps(base_state):
    """Test post_validation_router when state has steps remaining."""
    state = base_state.model_copy(update={
        "steps_to_run": [{"Step": 1, "Name": "Next Step"}]
    })
    result = post_validation_router(state)
    assert result == "run_workflow_step"

def test_post_validation_router_no_steps(base_state):
    """Test post_validation_router when state has no steps remaining."""
    state = base_state.model_copy(update={"steps_to_run": []})
    result = post_validation_router(state)
    assert result == "workflow_end"

def test_router_integration():
    """Test how routers work together in sequence."""
    # Initial state
    state = WorkflowState(
        description="Test integration",
        narrative_id=123,
        reads_id="test_reads",
        steps_to_run=[{"Step": 1, "Name": "First Step"}]
    )
    
    # Simulate workflow execution
    
    # Step 1: After analyst node
    next_node = analyst_router(state)
    assert next_node == "validate_step"
    
    # Step 2: After validation
    next_node = post_validation_router(state)
    assert next_node == "run_workflow_step"
    
    # Step 3: After running the step, remove steps to simulate completion
    state = state.model_copy(update={"steps_to_run": []})
    next_node = next_step_router(state)
    assert next_node == "workflow_end"
    
    # Alternative path: Error handling
    state = state.model_copy(update={"error": "Something failed", "steps_to_run": [{"Step": 2}]})
    next_node = next_step_router(state)
    assert next_node == "handle_error"