from ..service_client import ServiceClient

class ExecutionEngine(ServiceClient):
    default_endpoint: str = "https://kbase.us/services/ee2"
    _service = "execution_engine2"

    def __init__(self: "ExecutionEngine", token: str, endpoint: str=default_endpoint) -> "ExecutionEngine":
        super().__init__(endpoint, self._service, token)

    def check_job(self: "ExecutionEngine", job_id: str) -> dict:
        return self.simple_call("check_job", {"job_id": job_id})

    def run_job(self: "ExecutionEngine", job_submission: dict) -> str:
        return self.simple_call("run_job", job_submission)
