from typing import Optional, Type

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)

# Import things that are needed generically
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import BaseTool

from narrative_llm_agent.util.semantic import get_candidates, graph


description_query = """
MATCH (m:App|DataObject)
WHERE m.name = $candidate
WITH m, m.tooltip AS m_tooltip
MATCH (m)-[r]-(t)
WITH m, type(r) as type, collect(t.name) as names
WITH m, type+": "+reduce(s="", n IN names | s + n + ", ") as types
WITH m, collect(types) as contexts
WITH m, "type:" + labels(m)[0] + "\n" +
       reduce(s="", c in contexts | s + substring(c, 0, size(c)-2) +"\n") as context
WITH m, context + "\n" + "App name: " + m.name + "\n" + "Tooltip: " + m.tooltip + "\n" + "AppID: " + m.appid AS final_context
RETURN final_context LIMIT 1
"""

def get_information(entity: str, type: str) -> str:
    candidates = get_candidates(entity, type)
    if not candidates:
        return "No information was found about the KBase app in the database"
    elif len(candidates) > 1:
        newline = "\n"
        return (
            "Need additional information, which of these "
            f"did you mean: {newline + newline.join(str(d) for d in candidates)}"
        )
    data = graph.query(
        description_query, params={"candidate": candidates[0]["candidate"]}
    )
    print("candidate name provided=",candidates)
    return data[0]["final_context"]


class InformationInput(BaseModel):
    entity: str = Field(description="KBase app name mentioned in the question")
    entity_type: str = Field(
        description="type of the entity. Available options are 'AppCatalog' or 'AppCatalogRel'"
    )


class InformationTool(BaseTool):
    name = "Information"
    description = (
        "useful for when you need to answer questions about KBase apps"
    )
    args_schema: Type[BaseModel] = InformationInput

    def _run(
        self,
        entity: str,
        entity_type: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        return get_information(entity, entity_type)

    async def _arun(
        self,
        entity: str,
        entity_type: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool asynchronously."""
        return get_information(entity, entity_type)