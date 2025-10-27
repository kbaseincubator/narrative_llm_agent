import pytest
from unittest.mock import Mock, patch
from narrative_llm_agent.tools.job_tools import CompletedJob
from narrative_llm_agent.workflow_graph.graph import AnalysisWorkflow
from narrative_llm_agent.workflow_graph.nodes import WorkflowState

@pytest.fixture
def mock_workflow_nodes():
    with patch('narrative_llm_agent.workflow_graph.graph.WorkflowNodes') as mock_nodes:
        # Set up mock node functions
        mock_nodes.return_value.analyst_node = Mock()
        mock_nodes.return_value.app_runner_node = Mock()
        mock_nodes.return_value.workflow_validator_node = Mock()
        mock_nodes.return_value.handle_error = Mock()
        mock_nodes.return_value.workflow_end = Mock()
        yield mock_nodes

@pytest.fixture
def mock_state_graph():
    with patch('narrative_llm_agent.workflow_graph.graph.StateGraph') as mock_graph:
        mock_graph_instance = Mock()
        mock_graph.return_value = mock_graph_instance
        mock_graph_instance.add_node = Mock()
        mock_graph_instance.add_conditional_edges = Mock()
        mock_graph_instance.add_edge = Mock()
        mock_graph_instance.set_entry_point = Mock()
        mock_graph_instance.compile = Mock()
        yield mock_graph

def test_analysis_workflow_init(mock_workflow_nodes):
    """Test that AnalysisWorkflow initializes correctly"""
    workflow = AnalysisWorkflow(kbase_token="test_token")

    # Check that WorkflowNodes was initialized with the token
    mock_workflow_nodes.assert_called_once_with(
        "gpt-4.1-mini-cborg",
        "gpt-4.1-mini-cborg",
        "gpt-4.1-mini-cborg",
        "gpt-4.1-mini-cborg",
        "cborg",
        token="test_token",
        analyst_token=None,
        validator_token=None,
        app_flow_token=None,
        writer_token=None,
        embedding_token=None
    )

    # Check that the graph was built
    assert workflow.graph is not None

def test_build_graph(mock_workflow_nodes, mock_state_graph):
    """Test the graph building process"""
    workflow = AnalysisWorkflow(kbase_token="test_token")

    # Verify that StateGraph was created with WorkflowState
    mock_state_graph.assert_called_once_with(WorkflowState)

    # Verify that nodes were added
    mock_graph_instance = mock_state_graph.return_value
    assert mock_graph_instance.add_node.call_count == 5
    mock_graph_instance.add_node.assert_any_call("analyst", mock_workflow_nodes.return_value.analyst_node)
    mock_graph_instance.add_node.assert_any_call("run_workflow_step", mock_workflow_nodes.return_value.app_runner_node)
    mock_graph_instance.add_node.assert_any_call("validate_step", mock_workflow_nodes.return_value.workflow_validator_node)
    mock_graph_instance.add_node.assert_any_call("handle_error", mock_workflow_nodes.return_value.handle_error)
    mock_graph_instance.add_node.assert_any_call("workflow_end", mock_workflow_nodes.return_value.workflow_end)

    # Verify that conditional edges were added
    assert mock_graph_instance.add_conditional_edges.call_count == 3

    # Verify that direct edges were added
    assert mock_graph_instance.add_edge.call_count == 2

    # Verify that entry point was set
    mock_graph_instance.set_entry_point.assert_called_once_with("analyst")

    # Verify that graph was compiled
    mock_graph_instance.compile.assert_called_once()

@patch('narrative_llm_agent.workflow_graph.graph.StateGraph')
def test_run_workflow(mock_state_graph, mock_workflow_nodes):
    """Test running a workflow with parameters"""
    # Setup mock compiled graph
    mock_compiled_graph = Mock()
    mock_state_graph.return_value.compile.return_value = mock_compiled_graph
    mock_compiled_graph.invoke.return_value = {"results": "Test results"}

    # Create workflow and run it
    workflow = AnalysisWorkflow(kbase_token="test_token")
    result = workflow.run(narrative_id=123, reads_id="45/67/8", description="Test workflow")

    # Check that invoke was called with the right initial state
    expected_state = {
        "narrative_id": 123,
        "reads_id": "45/67/8",
        "description": "Test workflow",
        "analysis_plan": None,
        "steps_to_run": [],
        "completed_steps": [],
        "results": None,
        "error": None,
        "last_executed_step": {}
    }
    mock_compiled_graph.invoke.assert_called_once_with(expected_state)

    # Check that the result was returned correctly
    assert result == {"results": "Test results"}

def test_workflow_end_to_end():
    """Test an end-to-end workflow with mocked components"""
    with patch('narrative_llm_agent.workflow_graph.graph.WorkflowNodes') as mock_nodes:
        # Mock the node functions to modify state in predictable ways
        def mock_analyst(state):
            return state.model_copy(update={
                "steps_to_run": [{"Step": 1, "Name": "Test Step"}],
                "error": None
            })

        def mock_validator(state):
            return state.model_copy(update={
                "error": None
            })

        def mock_runner(state):
            # Consume a step and return updated state
            steps = state.steps_to_run
            current = steps[0]
            remaining = steps[1:] if len(steps) > 1 else []
            return state.model_copy(update={
                "steps_to_run": remaining,
                "last_executed_step": current,
                "step_result": CompletedJob(
                    narrative_id=123,
                    job_id="foo",
                    job_status="completed",
                    created_objects=[]
                ),
                "error": None
            })

        def mock_workflow_end(state):
            return state.model_copy(update={"results": "✅ Workflow complete."})

        # Assign mocks to the node functions
        mock_nodes.return_value.analyst_node = mock_analyst
        mock_nodes.return_value.workflow_validator_node = mock_validator
        mock_nodes.return_value.app_runner_node = mock_runner
        mock_nodes.return_value.workflow_end = mock_workflow_end

        # Create a real StateGraph but with mocked nodes
        workflow = AnalysisWorkflow(kbase_token="test_token")

        # Run the workflow
        result = workflow.run(
            narrative_id=123,
            reads_id="test_reads",
            description="Test workflow description"
        )

        # Verify the workflow completed successfully
        assert result["results"] == "✅ Workflow complete."
        assert "error" in result and result["error"] is None
