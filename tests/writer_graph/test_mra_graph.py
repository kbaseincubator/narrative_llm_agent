import pytest
from narrative_llm_agent.writer_graph.mra_graph import (
    MraWriterGraph,
)
from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.kbase.clients.execution_engine import ExecutionEngine
from narrative_llm_agent.writer_graph.writeup_state import WriteupState

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
        "narrative_llm_agent.writer_graph.mra_graph.get_llm", return_value=mock_llm
    )
    yield mock_get_llm


@pytest.fixture
def initial_state(mock_workspace):
    return WriteupState(
        narrative_data=MOCK_NARRATIVE_DATA, narrative_id=12345, ws_client=mock_workspace
    )


def test_writer_node(initial_state, mock_llm, mock_workspace, mock_execution_engine):
    """Test that writer_node correctly processes narrative data and generates a writeup."""
    writer = MraWriterGraph(mock_workspace, mock_execution_engine)
    result = writer.writer_node(initial_state)

    assert result.writeup_doc == "Test writeup document"
    assert result.error is None
    assert result.narrative_data == MOCK_NARRATIVE_DATA
    assert result.narrative_id == 12345


def test_checker_node_success(initial_state, mock_workspace, mock_execution_engine):
    """Test checker_node when narrative state is valid."""
    writer = MraWriterGraph(mock_workspace, mock_execution_engine)
    result = writer.checker_node(initial_state)

    assert result.error is None
    assert result.narrative_data == MOCK_NARRATIVE_DATA


def test_checker_node_error(initial_state, mock_workspace, mock_execution_engine):
    """Test checker_node when narrative state is invalid."""
    writer = MraWriterGraph(mock_workspace, mock_execution_engine)
    # Modify the state to simulate an error condition
    state_with_error = initial_state.model_copy(update={"error": "Test error"})
    result = writer.checker_node(state_with_error)

    assert result.error == "Test error"


def test_save_node(initial_state, mock_workspace, mock_execution_engine, mocker):
    """Test that save_node correctly saves the writeup document."""

    mock_workspace.save_objects.return_value = [[]]
    writer = MraWriterGraph(mock_workspace, mock_execution_engine)

    state_with_writeup = initial_state.model_copy(
        update={"writeup_doc": "Test writeup"}
    )
    result = writer.save_writeup(state_with_writeup)

    assert result.writeup_doc == "Test writeup"


def test_error_node(initial_state, mock_workspace, mock_execution_engine):
    """Test error_node correctly handles error state."""
    writer = MraWriterGraph(mock_workspace, mock_execution_engine)
    state_with_error = initial_state.model_copy(update={"error": "Test error"})
    result = writer.error(state_with_error)

    assert result.error == "Test error"


def test_check_analysis_state_error(mocker, mock_workspace, mock_execution_engine):
    """Test check_analysis_state routing logic."""
    # Test error state
    writer = MraWriterGraph(mock_workspace, mock_execution_engine)
    error_state = WriteupState(
        narrative_data="test",
        narrative_id=12345,
        error="Test error",
        ws_client=mocker.Mock(spec=Workspace),
    )
    assert writer.check_analysis_state(error_state) == "error"

def test_check_analysis_state_ok(mocker, mock_workspace, mock_execution_engine):
    """Test check_analysis_state routing logic."""
    # Test error state
    writer = MraWriterGraph(mock_workspace, mock_execution_engine)
    # Test success state
    success_state = WriteupState(
        narrative_data="test", narrative_id=12345, ws_client=mocker.Mock(spec=Workspace)
    )
    assert writer.check_analysis_state(success_state) == "ok"


def test_writer_graph_initialization(mock_workspace, mock_execution_engine):
    """Test WriterGraph initialization."""
    graph = MraWriterGraph(mock_workspace, mock_execution_engine)
    assert graph._workflow is not None
    assert graph._token is None


def test_writer_graph_run_workflow(
    mock_llm, initial_state, mock_workspace, mock_execution_engine, mocker
):
    narrative_id = 12345
    """Test the complete workflow execution."""
    mock_workspace.save_objects.return_value = [[]]
    mock_get_state = mocker.patch(
        "narrative_llm_agent.writer_graph.mra_graph.get_narrative_state",
        return_value=MOCK_NARRATIVE_DATA,
    )
    mocker.patch(
        "narrative_llm_agent.writer_graph.mra_graph.Workspace", return_value=mock_workspace
    )
    mocker.patch(
        "narrative_llm_agent.writer_graph.mra_graph.ExecutionEngine",
        return_value=mock_execution_engine,
    )
    graph = MraWriterGraph(mock_workspace, mock_execution_engine)
    graph.run_workflow(narrative_id)

    # Verify narrative state was retrieved
    mock_get_state.assert_called_once_with(narrative_id, mock_workspace, mock_execution_engine)


def test_writer_graph_error_handling(mocker, mock_workspace, mock_execution_engine):
    """Test error handling in the workflow."""
    graph = MraWriterGraph(mock_workspace, mock_execution_engine)

    mock_get_state = mocker.patch(
        "narrative_llm_agent.writer_graph.mra_graph.get_narrative_state",
        side_effect=Exception("Test error"),
    )
    with pytest.raises(Exception) as exc_info:
        graph.run_workflow(12345)

    assert str(exc_info.value) == "Test error"
    mock_get_state.assert_called_once()


def test_writeup_state_validation(mocker):
    """Test WriteupState model validation."""
    narrative_id = 12345
    # Test valid state
    valid_state = WriteupState(
        narrative_data="test", narrative_id=narrative_id, ws_client=mocker.Mock(spec=Workspace)
    )
    assert valid_state.narrative_id == narrative_id
    assert valid_state.narrative_data == "test"

    # Test invalid state (missing required fields)
    with pytest.raises(ValueError):
        WriteupState(
            narrative_data="test"
            # Missing ws_client
        )
