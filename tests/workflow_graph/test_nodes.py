import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import os
from narrative_llm_agent.workflow_graph.nodes import WorkflowNodes, WorkflowState, AnalysisStep

@pytest.fixture
def mock_llm_factory():
    """Mock the LLM factory function."""
    with patch('narrative_llm_agent.workflow_graph.nodes.get_llm') as mock_get_llm:
        mock_get_llm.return_value = Mock()
        yield mock_get_llm

@pytest.fixture
def mock_analyst_agent():
    """Mock the AnalystAgent class."""
    with patch('narrative_llm_agent.workflow_graph.nodes.AnalystAgent') as mock_agent:
        mock_agent_instance = Mock()
        mock_agent.return_value = mock_agent_instance
        mock_agent_instance.agent = Mock()
        yield mock_agent

@pytest.fixture
def mock_workflow_runner():
    """Mock the WorkflowRunner class."""
    with patch('narrative_llm_agent.workflow_graph.nodes.WorkflowRunner') as mock_runner:
        mock_runner_instance = Mock()
        mock_runner.return_value = mock_runner_instance
        mock_runner_instance.agent = Mock()
        yield mock_runner

@pytest.fixture
def mock_validator_agent():
    """Mock the WorkflowValidatorAgent class."""
    with patch('narrative_llm_agent.workflow_graph.nodes.WorkflowValidatorAgent') as mock_validator:
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance
        mock_validator_instance.agent = Mock()
        yield mock_validator

@pytest.fixture
def mock_task():
    """Mock the Task class."""
    with patch('narrative_llm_agent.workflow_graph.nodes.Task') as mock_task:
        mock_task_instance = Mock()
        mock_task.return_value = mock_task_instance
        yield mock_task

@pytest.fixture
def mock_crew():
    """Mock the Crew class."""
    with patch('narrative_llm_agent.workflow_graph.nodes.Crew') as mock_crew:
        mock_crew_instance = Mock()
        mock_crew.return_value = mock_crew_instance
        mock_crew_instance.kickoff.return_value = Mock(raw="{'continue_as_planned': true}")
        yield mock_crew

@pytest.fixture
def mock_extract_json():
    """Mock the extract_json functions."""
    with patch('narrative_llm_agent.workflow_graph.nodes.extract_json_from_string') as mock_extract_json:
        mock_extract_json.return_value = [{"Step": 1, "Name": "Test Step", "App": "TestApp"}]
        yield mock_extract_json

@pytest.fixture
def mock_extract_json_curly():
    """Mock the extract_json_from_string_curly functions."""
    with patch('narrative_llm_agent.workflow_graph.nodes.extract_json_from_string_curly') as mock_extract_json:
        mock_extract_json.return_value = {"continue_as_planned": True, "reasoning": "Test reasoning"}
        yield mock_extract_json

@pytest.fixture
def mock_analysis_pipeline():
    """Mock the AnalysisPipeline class."""
    with patch('narrative_llm_agent.workflow_graph.nodes.AnalysisPipeline') as mock_pipeline:
        yield mock_pipeline

@pytest.fixture
def workflow_nodes(mock_llm_factory):
    """Create a WorkflowNodes instance with a mock token."""
    os.environ["KB_AUTH_TOKEN"] = "mock_token"
    nodes = WorkflowNodes(token="mock_token")
    return nodes

def test_workflow_nodes_init_with_token():
    """Test initializing WorkflowNodes with a token."""
    nodes = WorkflowNodes(token="test_token")
    assert nodes.token == "test_token"

def test_workflow_nodes_init_from_env():
    """Test initializing WorkflowNodes from environment variable."""
    os.environ["KB_AUTH_TOKEN"] = "env_token"
    nodes = WorkflowNodes()
    assert nodes.token == "env_token"

def test_workflow_nodes_init_missing_token():
    """Test that initialization fails when token is missing."""
    if "KB_AUTH_TOKEN" in os.environ:
        del os.environ["KB_AUTH_TOKEN"]
    with pytest.raises(ValueError, match="KB_AUTH_TOKEN must be provided"):
        WorkflowNodes()

def test_analyst_node_success(workflow_nodes, mock_analyst_agent, mock_crew, mock_extract_json, mock_task, mock_analysis_pipeline):
    """Test the analyst_node function successfully creates an analysis plan."""
    # Create a state to pass to the node
    state = WorkflowState(
        description="Test genome analysis",
        narrative_id=123,
        reads_id="test_reads"
    )
    
    # Call the node function
    result = workflow_nodes.analyst_node(state)
    
    # Check that the analyst agent was created correctly
    mock_analyst_agent.assert_called_once()
    
    # Check that Task was created properly
    mock_task.assert_called_once()
    assert 'description' in mock_task.call_args[1]
    assert 'expected_output' in mock_task.call_args[1]
    assert 'output_json' in mock_task.call_args[1]
    assert 'agent' in mock_task.call_args[1]
    
    # Check that Crew was used to run the task
    mock_crew.assert_called_once()
    # Verify the Crew constructor arguments match your implementation
    crew_call_kwargs = mock_crew.call_args[1]
    assert 'agents' in crew_call_kwargs
    assert 'tasks' in crew_call_kwargs
    assert 'verbose' in crew_call_kwargs
    assert crew_call_kwargs['verbose'] is True
    
    # Check that the results were processed correctly
    mock_extract_json.assert_called_once()
    
    # Check that the state was updated correctly
    assert result.steps_to_run == [{"Step": 1, "Name": "Test Step", "App": "TestApp"}]
    assert result.error is None

def test_analyst_node_error(workflow_nodes, mock_analyst_agent, mock_crew, mock_task):
    """Test handling errors in the analyst_node function."""
    # Set up the mock crew to raise an exception
    mock_crew.return_value.kickoff.side_effect = Exception("Test error")
    
    # Create a state to pass to the node
    state = WorkflowState(
        description="Test genome analysis",
        narrative_id=123,
        reads_id="test_reads"
    )
    
    # Call the node function
    result = workflow_nodes.analyst_node(state)
    
    # Check error handling
    assert result.steps_to_run is None
    assert result.error == "Test error"

def test_workflow_runner_node_success(workflow_nodes, mock_workflow_runner, mock_crew, mock_task):
    """Test the workflow_runner_node function successfully executes a step."""
    # Create a state with steps to run
    state = WorkflowState(
        description="Test workflow",
        narrative_id=123,
        reads_id="test_reads",
        steps_to_run=[
            {"Step": 1, "Name": "Step 1", "App": "App1"},
            {"Step": 2, "Name": "Step 2", "App": "App2"}
        ],
        input_object_upa="1/2/3"
    )
    
    # Set up the mock crew result
    mock_crew.return_value.kickoff.return_value = Mock(raw="Step executed successfully")
    
    # Call the node function
    result = workflow_nodes.workflow_runner_node(state)
    
    # Check that WorkflowRunner was created correctly
    mock_workflow_runner.assert_called_once()
    
    # Check that Task was created
    mock_task.assert_called_once()
    
    # Check that Crew was used to run the task
    mock_crew.assert_called_once()
    # Verify it's using the implementation pattern with tasks list
    crew_call_kwargs = mock_crew.call_args[1]
    assert 'tasks' in crew_call_kwargs
    assert 'verbose' in crew_call_kwargs
    
    # Check that the state was updated correctly
    assert result.step_result is not None  # This will be the mock response
    assert len(result.steps_to_run) == 1
    assert result.steps_to_run[0]["Step"] == 2
    assert result.last_executed_step["Step"] == 1
    assert result.error is None

def test_workflow_runner_node_error(workflow_nodes, mock_workflow_runner, mock_crew, mock_task):
    """Test handling errors in the workflow_runner_node function."""
    # Set up the mock crew to raise an exception
    mock_crew.return_value.kickoff.side_effect = Exception("Execution error")
    
    # Create a state with steps to run
    state = WorkflowState(
        description="Test workflow",
        narrative_id=123,
        reads_id="test_reads",
        steps_to_run=[{"Step": 1, "Name": "Step 1", "App": "App1"}],
        input_object_upa="1/2/3"
    )
    
    # Call the node function
    result = workflow_nodes.workflow_runner_node(state)
    
    # Check error handling
    assert result.results is None
    assert result.error == "Execution error"

def test_workflow_validator_node_no_next_step(workflow_nodes):
    """Test the workflow_validator_node when there are no more steps to run."""
    # Create a state with no steps left to run
    state = WorkflowState(
        description="Test workflow",
        narrative_id=123,
        reads_id="test_reads",
        steps_to_run=[],
        last_executed_step={"Step": 1, "Name": "Final Step", "App": "FinalApp"},
        step_result="Final step executed"
    )
    
    # Call the node function
    result = workflow_nodes.workflow_validator_node(state)
    
    # Check that completion was recognized
    assert "Workflow complete" in result.results
    assert result.error is None

def test_workflow_validator_node_continue(workflow_nodes, mock_validator_agent, mock_crew, mock_extract_json_curly, mock_task):
    """Test the workflow_validator_node when continuing with the next step."""
    # Create a state with steps left to run
    state = WorkflowState(
        description="Test workflow",
        narrative_id=123,
        reads_id="test_reads",
        steps_to_run=[{"Step": 2, "Name": "Next Step", "App": "NextApp"}],
        last_executed_step={"Step": 1, "Name": "Previous Step", "App": "PrevApp"},
        step_result="Step executed successfully",
        input_object_upa="1/2/3"
    )
    
    # Set up the mock extraction to indicate continue as planned
    mock_extract_json_curly.return_value = {
        "continue_as_planned": True,
        "reasoning": "All looks good",
        "input_object_upa": "1/2/3/4"
    }
    
    # Call the node function
    result = workflow_nodes.workflow_validator_node(state)
    
    # Check that the validator was created correctly
    mock_validator_agent.assert_called_once()
    
    # Check that Task was created
    mock_task.assert_called_once()
    
    # Check that Crew was used to run the task
    mock_crew.assert_called_once()
    # Verify it's using the implementation pattern with tasks list
    crew_call_kwargs = mock_crew.call_args[1]
    assert 'tasks' in crew_call_kwargs
    assert 'verbose' in crew_call_kwargs
    
    # Check that JSON extraction was called
    mock_extract_json_curly.assert_called_once()
    
    # Check that the state was updated correctly
    assert result.error is None
    assert result.input_object_upa == "1/2/3/4"
    assert "validation_reasoning" in result.__dict__
    assert result.validation_reasoning == "All looks good"

def test_workflow_validator_node_modify(workflow_nodes, mock_validator_agent, mock_crew, mock_extract_json_curly, mock_task):
    """Test the workflow_validator_node when modifying the steps."""
    # Create a state with steps left to run
    state = WorkflowState(
        description="Test workflow",
        narrative_id=123,
        reads_id="test_reads",
        steps_to_run=[{"Step": 2, "Name": "Original Next Step", "App": "OrigApp"}],
        last_executed_step={"Step": 1, "Name": "Previous Step", "App": "PrevApp"},
        step_result="Step executed with warnings",
        input_object_upa="1/2/3"
    )
    
    # Set up the mock extraction to indicate modified steps
    modified_steps = [{"Step": 2, "Name": "Modified Step", "App": "ModApp"}]
    mock_extract_json_curly.return_value = {
        "continue_as_planned": False,
        "reasoning": "Need to modify approach due to warnings",
        "input_object_upa": "1/2/3/updated",
        "modified_next_steps": modified_steps
    }
    
    # Call the node function
    result = workflow_nodes.workflow_validator_node(state)
    
    # Check that the state was updated correctly with the modified steps
    assert result.error is None
    assert result.input_object_upa == "1/2/3/updated"
    assert result.steps_to_run == modified_steps
    assert result.validation_reasoning == "Need to modify approach due to warnings"

def test_workflow_validator_node_error(workflow_nodes, mock_validator_agent, mock_crew, mock_task):
    """Test handling errors in the workflow_validator_node function."""
    # Set up the mock crew to raise an exception
    mock_crew.return_value.kickoff.side_effect = Exception("Validation error")
    
    # Create a state with steps left to run
    state = WorkflowState(
        description="Test workflow",
        narrative_id=123,
        reads_id="test_reads",
        steps_to_run=[{"Step": 2, "Name": "Next Step", "App": "NextApp"}],
        last_executed_step={"Step": 1, "Name": "Previous Step", "App": "PrevApp"},
        step_result="Step executed"
    )
    
    # Call the node function
    result = workflow_nodes.workflow_validator_node(state)
    
    # Check error handling
    assert result.error == "Validation error"

def test_handle_error(workflow_nodes):
    """Test the handle_error function."""
    # Create a state with an error
    state = WorkflowState(
        description="Test workflow",
        narrative_id=123,
        reads_id="test_reads",
        error="Test error occurred"
    )
    
    # Call the node function
    result = workflow_nodes.handle_error(state)
    
    # Check that the error was properly recorded in results
    assert result.results == "Error: Test error occurred"

def test_workflow_end(workflow_nodes):
    """Test the workflow_end function."""
    # Create a state
    state = WorkflowState(
        description="Test workflow",
        narrative_id=123,
        reads_id="test_reads",
        results="Initial results"
    )
    
    # Call the node function
    result = workflow_nodes.workflow_end(state)
    
    # Check that the completion message was set
    assert result.results == "✅ Workflow complete."

def test_create_workflow_nodes():
    """Test the create_workflow_nodes helper function."""
    from narrative_llm_agent.workflow_graph.nodes import create_workflow_nodes
    
    # Call the function
    node_functions = create_workflow_nodes(token="test_token")
    
    # Check that it returns a dictionary with the expected keys
    assert isinstance(node_functions, dict)
    expected_keys = ["analyst_node", "workflow_runner_node", "workflow_validator_node", "handle_error", "workflow_end"]
    for key in expected_keys:
        assert key in node_functions
        assert callable(node_functions[key])