from crewai import Agent

from narrative_llm_agent.tools.job_tools import job_status

def job_agent(llm) -> Agent:
    return Agent(
        role="Job Manager",
        goal="Manage app and job running and tracking in the KBase system. Start and monitor jobs using the KBase Execution engine.",
        backstory="""You are an expert computer engineer. You are responsible for initializing, running, and monitoring
        KBase applications using the Execution Engine. You work with the rest of your crew to run bioinformatics and
        data science analyses, handle job states, and return results.""",
        verbose=True,
        tools=[
            job_status,
        ],
        llm=llm,
        allow_delegation=False
    )
