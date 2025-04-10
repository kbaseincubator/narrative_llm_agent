from narrative_llm_agent.kbase.clients.workspace import Workspace
from narrative_llm_agent.util.narrative import NarrativeUtil


def create_markdown_cell(
    narrative_id: int, text: str, ws: Workspace
) -> str:
    """Stores results of a conversation in a Narrative markdown cell. This uses the narrative id
    to pull the narrative from the workspace, create the new markdown cell at the bottom,
    and save it again. It returns a simple message when complete, or throws an Exception if it
    fails."""
    narr_util = NarrativeUtil(ws)
    narr = narr_util.get_narrative_from_wsid(narrative_id)
    narr.add_markdown_cell(text)
    narr_util.save_narrative(narr, narrative_id)
    return "Conversation successfully stored."
