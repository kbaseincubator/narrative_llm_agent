import pytest
from narrative_llm_agent.writer_graph.summary_graph import (
    SummaryWriterGraph,
    SummaryWriteupState,
)
from narrative_llm_agent.kbase.clients.workspace import Workspace

# Mock data for testing
MOCK_NARRATIVE_DATA = [
    "This is a test narrative with some genomic analysis results.",
    """App: Assembly
    - Input: reads.fastq
    - Output: assembly.fasta
    - Status: completed""",
    """App: Annotation
    - Input: assembly.fasta
    - Output: annotation.gff
    - Status: completed""",
]
WRITER_LLM = "gpt-o1-cborg"

@pytest.fixture
def mock_llm(mocker):
    mock_llm = mocker.Mock()
    mock_llm.invoke.return_value.content = "Test writeup document"
    mock_get_llm = mocker.patch(
        "narrative_llm_agent.writer_graph.summary_graph.get_llm", return_value=mock_llm
    )
    yield mock_get_llm


@pytest.fixture
def initial_state(mock_workspace):
    return SummaryWriteupState(
        narrative_markdown=MOCK_NARRATIVE_DATA,
        narrative_id=12345,
        ws_client=mock_workspace,
        app_list=["kb_quast/run_QUAST_app"],
    )


def test_writer_node(initial_state, mock_llm, mock_workspace):
    """Test that writer_node correctly processes narrative data and generates a writeup."""
    writer = SummaryWriterGraph(mock_workspace, WRITER_LLM)
    result = writer.summary_writer_node(initial_state)

    assert result.writeup_doc == "Test writeup document"
    assert result.error is None
    assert result.narrative_markdown == MOCK_NARRATIVE_DATA
    assert result.narrative_id == 12345


def test_save_node(initial_state, mock_workspace, mocker):
    """Test that save_node correctly saves the writeup document."""

    mock_workspace.save_objects.return_value = [[]]
    writer = SummaryWriterGraph(mock_workspace, WRITER_LLM)

    state_with_writeup = initial_state.model_copy(
        update={"writeup_doc": "Test writeup"}
    )
    result = writer.save_writeup(state_with_writeup)

    assert result.writeup_doc == "Test writeup"


def test_writer_graph_initialization(mock_workspace):
    """Test WriterGraph initialization."""
    graph = SummaryWriterGraph(mock_workspace, WRITER_LLM)
    assert graph._workflow is not None
    assert graph._token is None


def test_writer_graph_run_workflow(mock_llm, initial_state, mock_workspace, mocker):
    narrative_id = 12345
    """Test the complete workflow execution."""
    mock_workspace.save_objects.return_value = [[]]
    mock_get_md = mocker.patch(
        "narrative_llm_agent.writer_graph.summary_graph.get_all_markdown_text",
        return_value=MOCK_NARRATIVE_DATA,
    )
    mocker.patch(
        "narrative_llm_agent.writer_graph.summary_graph.Workspace",
        return_value=mock_workspace,
    )
    graph = SummaryWriterGraph(mock_workspace, WRITER_LLM)
    graph.run_workflow(narrative_id, ["foobar/baz"])

    # Verify narrative state was retrieved
    mock_get_md.assert_called_once_with(narrative_id, mock_workspace)


def test_writer_graph_error_handling(mocker, mock_workspace):
    """Test error handling in the workflow."""
    graph = SummaryWriterGraph(mock_workspace, WRITER_LLM)

    mock_get_md = mocker.patch(
        "narrative_llm_agent.writer_graph.summary_graph.get_all_markdown_text",
        side_effect=Exception("Test error"),
    )
    with pytest.raises(Exception) as exc_info:
        graph.run_workflow(12345, ["foobar/baz"])

    assert str(exc_info.value) == "Test error"
    mock_get_md.assert_called_once()


def test_writeup_state_validation(mocker):
    """Test SummaryWriteupState model validation."""
    narrative_id = 12345
    # Test valid state
    valid_state = SummaryWriteupState(
        narrative_markdown=["test"],
        narrative_id=narrative_id,
        ws_client=mocker.Mock(spec=Workspace),
        app_list=[],
    )
    assert valid_state.narrative_id == narrative_id
    assert valid_state.narrative_markdown == ["test"]

    # Test invalid state (missing required fields)
    with pytest.raises(ValueError):
        SummaryWriteupState(
            narrative_markdown=["test"]
            # Missing ws_client
        )
