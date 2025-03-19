from typing import Optional, Type, List, Tuple
from langchain.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from pydantic import BaseModel, Field, PrivateAttr
from langchain.tools import BaseTool
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from neo4j import GraphDatabase

description_query = """
MATCH (m:App|DataObject)
WHERE m.name CONTAINS $candidate
OPTIONAL MATCH (m)-[r]-(t)
WITH m, type(r) as rel_type, collect(t.name) as names
WITH m, rel_type + ": " + reduce(s="", n IN names | s + n + ", ") as contexts
WITH m, CASE WHEN size(collect(contexts)) = 0 THEN ["No related data object nodes found"] ELSE collect(contexts) END as contexts_list
WITH m, reduce(s="", c IN contexts_list | s + substring(c, 0, size(c)-2) + "\n") as all_contexts
RETURN "type: " + labels(m)[0] + "\n" +
       all_contexts +
       "App name: " + m.name + "\n" +
       "Tooltip: " + m.tooltip + "\n" +
       "AppID: " + m.appid
LIMIT 1
"""

def calculate_cosine_similarity(entity: str, app_names: List[str]) -> List[Tuple[str, float]]:
    vectorizer = TfidfVectorizer().fit_transform([entity] + app_names)
    vectors = vectorizer.toarray()
    input_vector = vectors[0]
    app_vectors = vectors[1:]
    similarities = cosine_similarity([input_vector], app_vectors).flatten()
    ranked_apps = sorted(zip(app_names, similarities), key=lambda x: x[1], reverse=True)
    print('ranked_apps:',ranked_apps[0][0])
    return ranked_apps


class InformationInput(BaseModel):
    entity: str = Field(description="KBase app name mentioned in the question")
    entity_type: str = Field(description="type of the entity. Available options are 'AppCatalog' or 'AppCatalogRel'")

class InformationTool(BaseTool):
    name: str = "Information"
    description: str = "useful for when you need to answer questions about KBase apps"
    args_schema: Type[BaseModel] = InformationInput
    _driver: GraphDatabase.driver = PrivateAttr()
    def __init__(self, uri: str, user: str, password: str, **kwargs):
        super().__init__(**kwargs)
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def fetch_app_names(self) -> List[str]:
        query = "MATCH (app:App) RETURN app.name AS name"
        with self._driver.session() as session:
            result = session.run(query)
            return [record["name"] for record in result]

    def fetch_app_description(self,entity:str) -> str:
        with self._driver.session() as session:
            app_names = self.fetch_app_names()
            app_name = calculate_cosine_similarity(entity, app_names)[0][0]
            result = session.run(description_query, candidate=app_name)
            app_description = result.single()[0]
            return app_description

    def _run(self, entity: str, entity_type: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        return self.fetch_app_description(entity)

    async def _arun(self, entity: str, entity_type: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        return self.fetch_app_description(entity)

    def __del__(self):
        self._driver.close()
