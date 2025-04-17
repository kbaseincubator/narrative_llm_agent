from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.tools.narrative_tools import create_markdown_cell
from narrative_llm_agent.util.narrative import NarrativeUtil


def test_create_markdown_cell(mocker, test_narrative_object):
    ws_id = 123
    conversation = "This is very important."
    narr = test_narrative_object
    get_mock = mocker.patch.object(
        NarrativeUtil, "get_narrative_from_wsid", return_value=narr
    )
    save_mock = mocker.patch.object(NarrativeUtil, "save_narrative", return_value=[])
    num_cells = len(narr.cells)
    resp = create_markdown_cell(ws_id, conversation, mocker.Mock(spec=Workspace))
    assert resp == "Conversation successfully stored."
    get_mock.assert_called_once_with(ws_id)
    save_mock.assert_called_once_with(narr, ws_id)
    assert len(narr.cells) == num_cells + 1
    assert narr.cells[-1].source == conversation


