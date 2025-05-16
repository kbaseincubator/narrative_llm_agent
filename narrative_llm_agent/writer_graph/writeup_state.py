from pydantic import BaseModel, ConfigDict

class WriteupState(BaseModel):
    """
    Includes a Workspace client that can get passed around the nodes,
    to avoid nodes having to deal with auth.
    Though I guess that's implicit with the Workspace...
    """
    narrative_data: str
    narrative_id: int
    writeup_doc: str | None = None
    error: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
