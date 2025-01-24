from pydantic import BaseModel

from narrative_llm_agent.kbase.clients.execution_engine import JobState

class Singleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = super(Singleton, cls).__new__(cls, *args, **kwargs)
        return cls._instance


class MockJob(BaseModel):
    narrative_id: int
    app_id: str
    params: dict
    job_submission: dict
    job_id: str

class KBaseMock(Singleton):
    _jobs: dict[str, MockJob] = {}

    def mock_run_job(self: "KBaseMock", narrative_id: int, app_id: str, params: dict, job_submission: dict) -> str:
        job_id = f"mock_job_{len(self._jobs)+1}"
        mock_job = MockJob(
            job_id=job_id,
            narrative_id=narrative_id,
            app_id=app_id,
            params=params,
            job_submission=job_submission
        )
        self._jobs[job_id] = mock_job
        return job_id

    def get_mock_job(self: "KBaseMock", job_id: str) -> MockJob:
        if job_id not in self._jobs:
            raise ValueError(f"job id '{job_id}' not found")
        return self._jobs[job_id]

    def check_mock_job(self: "KBaseMock", job_id: str) -> JobState:
        if job_id not in self._jobs:
            raise ValueError(f"job id '{job_id}' unknown")
        #TODO
        return
