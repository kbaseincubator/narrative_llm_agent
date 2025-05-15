import pytest
from narrative_llm_agent.writer_graph.graph import (
    WriterGraph,
    WriteupState,
    writer_node,
    checker_node,
    save_node,
    error_node,
    check_analysis_state,
)
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine

# Mock data for testing
MOCK_NARRATIVE_DATA = """
This is a test narrative with some genomic analysis results.
App: Assembly
- Input: reads.fastq
- Output: assembly.fasta
- Status: completed

App: Annotation
- Input: assembly.fasta
- Output: annotation.gff
- Status: completed
"""


@pytest.fixture
def mock_execution_engine(mocker):
    return mocker.Mock(spec=ExecutionEngine)


@pytest.fixture
def mock_llm(mocker):
    mock_llm = mocker.Mock()
    mock_llm.invoke.return_value.content = "Test writeup document"
    mock_get_llm = mocker.patch(
        "narrative_llm_agent.writer_graph.graph.get_llm", return_value=mock_llm
    )
    yield mock_get_llm


@pytest.fixture
def initial_state(mock_workspace):
    return WriteupState(
        narrative_data=MOCK_NARRATIVE_DATA, narrative_id=12345, ws_client=mock_workspace
    )


def test_writer_node(initial_state, mock_llm):
    """Test that writer_node correctly processes narrative data and generates a writeup."""
    result = writer_node(initial_state)

    assert result.writeup_doc == "Test writeup document"
    assert result.error is None
    assert result.narrative_data == MOCK_NARRATIVE_DATA
    assert result.narrative_id == 12345


def test_checker_node_success(initial_state):
    """Test checker_node when narrative state is valid."""
    result = checker_node(initial_state)

    assert result.error is None
    assert result.narrative_data == MOCK_NARRATIVE_DATA


def test_checker_node_error(initial_state):
    """Test checker_node when narrative state is invalid."""
    # Modify the state to simulate an error condition
    state_with_error = initial_state.model_copy(update={"error": "Test error"})
    result = checker_node(state_with_error)

    assert result.error == "Test error"


def test_save_node(initial_state, mock_workspace, mocker):
    """Test that save_node correctly saves the writeup document."""

    mock_workspace.save_objects.return_value = [[]]

    state_with_writeup = initial_state.model_copy(
        update={"writeup_doc": "Test writeup"}
    )
    result = save_node(state_with_writeup)

    assert result.writeup_doc == "Test writeup"


def test_error_node(initial_state):
    """Test error_node correctly handles error state."""
    state_with_error = initial_state.model_copy(update={"error": "Test error"})
    result = error_node(state_with_error)

    assert result.error == "Test error"


def test_check_analysis_state(mocker):
    """Test check_analysis_state routing logic."""
    # Test error state
    error_state = WriteupState(
        narrative_data="test",
        narrative_id=12345,
        error="Test error",
        ws_client=mocker.Mock(spec=Workspace),
    )
    assert check_analysis_state(error_state) == "error"

    # Test success state
    success_state = WriteupState(
        narrative_data="test", narrative_id=12345, ws_client=mocker.Mock(spec=Workspace)
    )
    assert check_analysis_state(success_state) == "ok"


def test_writer_graph_initialization():
    """Test WriterGraph initialization."""
    graph = WriterGraph(12345)
    assert graph._narrative_id == 12345
    assert graph._workflow is not None


def test_writer_graph_run_workflow(
    mock_llm, initial_state, mock_workspace, mock_execution_engine, mocker
):
    """Test the complete workflow execution."""
    mock_workspace.save_objects.return_value = [[]]
    mock_get_state = mocker.patch(
        "narrative_llm_agent.writer_graph.graph.get_narrative_state",
        return_value=MOCK_NARRATIVE_DATA,
    )
    mocker.patch(
        "narrative_llm_agent.writer_graph.graph.Workspace", return_value=mock_workspace
    )
    mocker.patch(
        "narrative_llm_agent.writer_graph.graph.ExecutionEngine",
        return_value=mock_execution_engine,
    )
    graph = WriterGraph(12345)
    graph.run_workflow()

    # Verify narrative state was retrieved
    mock_get_state.assert_called_once_with(12345, mock_workspace, mock_execution_engine)


def test_writer_graph_error_handling(mocker):
    """Test error handling in the workflow."""
    mock_get_state = mocker.patch(
        "narrative_llm_agent.writer_graph.graph.get_narrative_state",
        side_effect=Exception("Test error"),
    )
    graph = WriterGraph(12345)
    with pytest.raises(Exception) as exc_info:
        graph.run_workflow()

    assert str(exc_info.value) == "Test error"
    mock_get_state.assert_called_once()


def test_writeup_state_validation(mocker):
    """Test WriteupState model validation."""
    # Test valid state
    valid_state = WriteupState(
        narrative_data="test", narrative_id=12345, ws_client=mocker.Mock(spec=Workspace)
    )
    assert valid_state.narrative_id == 12345
    assert valid_state.narrative_data == "test"

    # Test invalid state (missing required fields)
    with pytest.raises(ValueError):
        WriteupState(
            narrative_data="test",
            narrative_id=12345,
            # Missing ws_client
        )
