from pydantic import BaseModel, Field
from langchain.tools import tool
from narrative_llm_agent.agents.kbase_agent import KBaseAgent
from narrative_llm_agent.crews.job_crew import JobCrew
from crewai import Agent

class AppRunInputs(BaseModel):
    narrative_id: int = Field(description="The id of the narrative where the app will run.")
    app_id: str = Field(description="The id of the app to run, formalized as module_name/app_name.")
    input_object_upa: str = Field("The UPA of the input object, with the pattern number/number/number.")

class WorkflowRunner(KBaseAgent):
    job_crew: JobCrew
    role: str = "KBase workflow runner"
    goal: str = "Your goal is to create and run elegant and scientifically meaningful computational biology workflows."
    backstory: str = "You are a dedicated and effective computational biologist. You have deep knowledge of how to run workflows in the DOE KBase system and have years of experience using this to produce high quality scientific knowledge."

    def __init__(self, llm, token: str = None):
        self.job_crew = JobCrew(llm)
        self._llm = llm
        self._token = token

        @tool("Run KBase app", args_schema=AppRunInputs)
        def do_app_run(narrative_id: int, app_id: str, input_object_upa: str) -> str:
            """
            This invokes a CrewAI crew to run a new KBase app from start to finish and
            returns the results. It takes in the narrative_id, app_id (formalized as module_name/app_name), and
            UPA of the input object.
            """
            print(f"starting an app run: {narrative_id} {app_id} {input_object_upa}")
            try:
                result = self.job_crew.start_job(app_id, input_object_upa, narrative_id, app_id=app_id)
                print(f"finished app run: {narrative_id} {app_id} {input_object_upa}")
            except Exception as e:
                print("[JOB ERROR]", e)
                import traceback
                traceback.print_exc()
                traceback.print_stack()
            print(result)
            return result

        self.agent = Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            tools=[do_app_run],
            llm=self._llm,
            allow_delegation=False,
            memory=True,
        )
