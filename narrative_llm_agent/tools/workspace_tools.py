from narrative_llm_agent.kbase.clients.workspace import Workspace


def get_object_metadata(obj_upa: str, ws: Workspace) -> dict[str, str]:
    """Gets object metadata from a KBase UPA string as a dict."""
    # look up object info first, get metadata from that to form a prompt.
    # then have the agent converse with the user.
    obj_info = ws.get_object_info(obj_upa)
    return obj_info.metadata
