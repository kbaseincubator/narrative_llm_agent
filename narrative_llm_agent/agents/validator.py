from crewai import Agent
from narrative_llm_agent.agents.kbase_agent import KBaseAgent

class WorkflowValidatorAgent(KBaseAgent):
    role: str = "You are a workflow validator, responsible for analyzing app run results and determining next steps."
    goal: str = "Ensure that each step in a computational biology workflow produces expected results and that subsequent steps are appropriate."
    backstory: str = """You are an experienced computational biologist with deep expertise in KBase workflows. 
    You analyze results from each step and determine if the workflow should continue as planned or be modified based on input/output data objects for the apps."""
    
    def __init__(self, llm, token: str = None):
        self._llm = llm
        self._token = token
        
        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            llm=self._llm,
            allow_delegation=False,
            memory=True,
        )