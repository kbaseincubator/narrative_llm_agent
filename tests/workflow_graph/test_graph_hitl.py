import pytest
from unittest.mock import Mock, patch
from narrative_llm_agent.tools.job_tools import CompletedJob
from narrative_llm_agent.workflow_graph.graph_hitl import AnalysisWorkflow, WorkflowCallback
from narrative_llm_agent.workflow_graph.nodes_hitl import WorkflowState

@pytest.fixture
def mock_workflow_nodes():
    with patch('narrative_llm_agent.workflow_graph.graph_hitl.WorkflowNodes') as mock_nodes:
        # Set up mock node functions
        mock_nodes.return_value.analyst_node = Mock()
        mock_nodes.return_value.human_approval_node = Mock()
        mock_nodes.return_value.app_runner_node = Mock()
        mock_nodes.return_value.workflow_validator_node = Mock()
        mock_nodes.return_value.handle_error = Mock()
        mock_nodes.return_value.workflow_end = Mock()
        yield mock_nodes

@pytest.fixture
def mock_state_graph():
    with patch('narrative_llm_agent.workflow_graph.graph_hitl.StateGraph') as mock_graph:
        mock_graph_instance = Mock()
        mock_graph.return_value = mock_graph_instance
        mock_graph_instance.add_node = Mock()
        mock_graph_instance.add_conditional_edges = Mock()
        mock_graph_instance.add_edge = Mock()
        mock_graph_instance.set_entry_point = Mock()
        mock_graph_instance.compile = Mock()
        yield mock_graph


class TestWorkflowCallback:
    def test_workflow_callback(self):
        mock_logger = Mock()
        cb = WorkflowCallback(mock_logger)

        cb.on_chain_start({}, {"key1": "val1", "key2": "val2"})
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "WORKFLOW STARTED" in call_args
        assert "key1" in call_args
        assert "key2" in call_args

    def test_on_chain_end(self):
        mock_logger = Mock()
        callback = WorkflowCallback(mock_logger)
        callback.on_chain_end({})

        mock_logger.info.assert_called_once_with("WORKFLOW COMPLETED")

    def test_on_chain_error(self):
        mock_logger = Mock()
        callback = WorkflowCallback(mock_logger)
        error = Exception("Test error message")

        callback.on_chain_error(error)

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "WORKFLOW ERROR" in call_args
        assert "Test error message" in call_args


class TestAnalysisWorkflow:
    def test_analysis_workflow_init(self, mock_workflow_nodes):
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

    def test_build_graph(self, mock_workflow_nodes, mock_state_graph):
        """Test the graph building process"""
        workflow = AnalysisWorkflow(kbase_token="test_token")

        # Verify that StateGraph was created with WorkflowState
        mock_state_graph.assert_called_once_with(WorkflowState)

        # Verify that nodes were added
        mock_graph_instance = mock_state_graph.return_value
        assert mock_graph_instance.add_node.call_count == 3
        # mock_graph_instance.add_node.assert_any_call("analyst", mock_workflow_nodes.return_value.analyst_node)
        # mock_graph_instance.add_node.assert_any_call("human_approval", mock_workflow_nodes.return_value.self.human_approval_node)
        # mock_graph_instance.add_node.assert_any_call("handle_error", mock_workflow_nodes.return_value.handle_error)

        # Verify that conditional edges were added
        assert mock_graph_instance.add_conditional_edges.call_count == 1

        # Verify that direct edges were added
        assert mock_graph_instance.add_edge.call_count == 2

        # Verify that entry point was set
        mock_graph_instance.set_entry_point.assert_called_once_with("analyst")

        # Verify that graph was compiled
        mock_graph_instance.compile.assert_called_once()

    @patch('narrative_llm_agent.workflow_graph.graph_hitl.StateGraph')
    def test_run_workflow(self, mock_state_graph, mock_workflow_nodes):
        """Test running a workflow with parameters"""
        # Setup mock compiled graph
        mock_compiled_graph = Mock()
        mock_state_graph.return_value.compile.return_value = mock_compiled_graph
        mock_compiled_graph.invoke.return_value = {"results": "Test results"}

        # Create workflow and run it
        workflow = AnalysisWorkflow(kbase_token="test_token")
        narrative_id = 123
        reads_id = "45/67/8"
        description = "test workflow"
        result = workflow.run(narrative_id=narrative_id, reads_id=reads_id, description=description)

        expected_state = {
            "narrative_id": narrative_id,
            "reads_id": reads_id,
            "description": description,
            "steps_to_run": [],
            "completed_steps": [],
            "results": None,
            "error": None,
            "last_executed_step": {},
            "awaiting_approval": False,
            "human_approval_status": None,
            "human_feedback": None,
        }
        mock_compiled_graph.invoke.assert_called_once_with(expected_state)

        # Check that the result was returned correctly
        assert result == {"results": "Test results"}

    def test_analysis_workflow_end_to_end_ok(self):
        """
        Mock the nodes and test that the routing and state management passes
        through correctly.
        """
        with patch("narrative_llm_agent.workflow_graph.graph_hitl.WorkflowNodes") as mock_nodes:
            def mock_analyst(state):
                return state.model_copy(update={
                    "steps_to_run": [{"Step": 1, "Name": "Test Step"}],
                    "error": None
                })

            def mock_human_approval(state):
                return state.model_copy(update={
                    "awaiting_approval": False,
                    "human_feedback": "looks good!",
                    "error": None
                })

            def mock_handle_error(state):
                # no-op in this case
                return state

            mock_nodes.return_value.analyst_node = mock_analyst
            mock_nodes.return_value.human_approval_node = mock_human_approval
            mock_nodes.return_value.handle_error = mock_handle_error

            # Create a real StateGraph but with mocked nodes
            workflow = AnalysisWorkflow(kbase_token="test_token")

            # Run the workflow
            result = workflow.run(
                narrative_id=123,
                reads_id="test_reads",
                description="Test workflow description"
            )

            expected_state = {
                "steps_to_run": [{"Step": 1, "Name": "Test Step"}],
                "error": None,
                "awaiting_approval": False,
                "human_feedback": "looks good!",
                "description": "Test workflow description",
                "last_executed_step": {},
                "completed_steps": [],
                "narrative_id": 123,
                "reads_id": "test_reads",
                "results": None,
                "human_approval_status": None
            }
            print(result)
            # Verify the workflow completed successfully
            assert result == expected_state



def test_execution_workflow_end_to_end():
    """Test an end-to-end workflow with mocked components"""
    with patch('narrative_llm_agent.workflow_graph.graph_hitl.WorkflowNodes') as mock_nodes:
        # Mock the node functions to modify state in predictable ways
        def mock_analyst(state):
            return state.model_copy(update={
                "steps_to_run": [{"Step": 1, "Name": "Test Step"}],
                "error": None
            })

        def mock_human_approval(state):
            return state.model_copy(update={
                "awaiting_approval": False,
                "human_feedback": "looks good!",
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
        mock_nodes.return_value.human_approval_node = mock_human_approval
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
