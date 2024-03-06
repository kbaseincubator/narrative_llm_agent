from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import BaseTool, tool


class AnalystInput(BaseModel):
    input: str = Field(description="query to look up KBase documentation, catalog or tutorials")