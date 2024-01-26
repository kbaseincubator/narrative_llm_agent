from crewai import Agent
from narrative_llm_agent.tools.narrative_tools import fetch_narrative_objects

def narrative_agent(llm) -> Agent:
    return Agent(
        role="Bioinformaticist and Data Scientist",
        goal="Retrieve data from the KBase system. Filter and interpret datasets as necessary to achieve team goals.",
        backstory="""You are an expert in bioinformatics and data science, with years of experience working with the DoE KBase system.
        You are responsible for interacting with the KBase Narrative interface on behalf of your crew.
        These interfactions will include uploading and downloading data, running analyses, and retrieving results.""",
        verbose=True,
        tools=[
            fetch_narrative_objects,
        ],
        llm=llm,
        allow_delegation=False
    )
