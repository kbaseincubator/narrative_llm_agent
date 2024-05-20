from ..service_client import ServiceClient
import json

class NarrativeCellInfo:
    cell_id: str
    run_id: str
    app_version_tag: str

    def __init__(self, data: dict) -> None:
        self.cell_id = data.get("cell_id")
        self.run_id = data.get("run_id")
        self.app_version_tag = data.get("tag")

    def to_dict(self) -> dict:
        dict_form = {}
        for key, value in vars(self).items():
            dict_form[key] = value
        return dict_form

class JobInput:
    method: str
    app_id: str
    params: list[dict]
    service_ver: str
    source_ws_objects: list[str]
    meta: dict
    ws_id: int
    parent_job_id: str | None
    cell_info: NarrativeCellInfo

    def __init__(self, data: dict) -> None:
        required_fields = ["method", "app_id", "params", "service_ver"]
        missing = [field for field in required_fields if field not in data]
        if len(missing):
            raise KeyError(f"JobInput data is missing required fields {missing}")

        self.method = data["method"]
        self.app_id = data["app_id"]
        self.params = data["params"]
        self.service_ver = data["service_ver"]
        self.source_ws_objects = data.get("source_ws_objects", [])
        self.meta = data.get("meta", {})
        self.ws_id = data.get("wsid", 0)
        self.parent_job_id = data.get("parent_job_id")
        if "narrative_cell_info" in data:
            self.narrative_cell_info = NarrativeCellInfo(data["narrative_cell_info"])
        else:
            self.narrative_cell_info = None

    def to_dict(self) -> dict:
        """
        Add something about narrative cell info in here somewhere that's not actually in the spec.
        """
        dict_form = {}
        for key, value in vars(self).items():
            dict_form[key] = value
        if self.narrative_cell_info is not None:
            dict_form["narrative_cell_info"] = self.narrative_cell_info.to_dict()
        return dict_form

    def __str__(self) -> str:
        return json.dumps(self.to_dict())

class JsonRpcError:
    name: str
    code: int
    message: str
    error: str

    def __init__(self, name: str, code: int, message: str, error: str) -> None:
        self.name = name
        self.code = code
        self.message = message
        self.error = error

    def to_dict(self):
        return { key: getattr(self, key) for key in ["name", "code", "message", "error"] }

class JobState:
    job_id: str
    user: str
    ws_id: int
    status: str
    job_input: JobInput
    created: int
    queued: int
    estimating: int
    running: int
    finished: int
    updated: int
    error: JsonRpcError | None
    error_code: int | None
    errormsg: str | None
    terminated_code: int
    batch_id: str | None
    batch_job: bool
    child_jobs: list[str]
    retry_count: int
    retry_ids: list[str]

    def __init__(self, data: dict) -> None:
        """
        Creates a simple object for holding and validating job states.
        If any required fields are missing, this raises a KeyError.
        """
        required_fields = ["job_id", "user", "wsid", "status", "job_input"]
        missing = [field for field in required_fields if field not in data]
        if len(missing):
            raise KeyError(f"JobState data is missing required field(s) {','.join(missing)}")

        self.job_id = data["job_id"]
        self.user = data["user"]
        self.ws_id = data["wsid"]
        self.status = data["status"]
        self.job_input = JobInput(data["job_input"])
        self.created = data.get("created", 0)
        self.queued = data.get("queued", 0)
        self.estimating = data.get("estimating", 0)
        self.running = data.get("running", 0)
        self.finished = data.get("finished", 0)
        self.updated = data.get("updated", 0)
        if "error" in data:
            err = data["error"]
            self.error = JsonRpcError(err.get("name"), err.get("code"), err.get("message"), err.get("error"))
        else:
            self.error = None
        self.error_code = data.get("error_code")
        self.errormsg = data.get("errormsg")
        self.terminated_code = data.get("terminated_code")
        self.batch_id = data.get("batch_id")
        self.batch_job = data.get("batch_job", False)
        self.child_jobs = data.get("child_jobs", [])
        self.retry_count = data.get("retry_count", 0)
        self.retry_ids = data.get("retry_ids", [])

    def to_dict(self) -> dict:
        required = ["job_id", "user", "status", "ws_id", "child_jobs", "batch_job"]
        dict_form = {key: getattr(self, key) for key in required}

        time_keys = ["created", "queued", "estimating", "running", "finished", "updated"]
        for key in time_keys:
            if getattr(self, key) is not None and getattr(self, key) > 0:
                dict_form[key] = getattr(self, key)

        dict_form["job_input"] = self.job_input.to_dict()
        if self.error is not None:
            dict_form["error"] = self.error.to_dict()

        optionals = ["error_code", "errormsg", "terminated_code", "batch_id"]
        for key in optionals:
            if getattr(self, key) is not None:
                dict_form[key] = getattr(self, key)

        return dict_form

    def __str__(self) -> str:
        return json.dumps(self.to_dict())

    def __eq__(self, other) -> bool:
        if not isinstance(other, JobState):
            return False
        return self.to_dict() == other.to_dict()

class ExecutionEngine(ServiceClient):
    default_endpoint: str = "https://kbase.us/services/ee2"
    _service: str = "execution_engine2"

    def __init__(self: "ExecutionEngine", token: str, endpoint: str=default_endpoint) -> None:
        super().__init__(endpoint, self._service, token)

    def check_job(self: "ExecutionEngine", job_id: str) -> JobState:
        return JobState(self.simple_call("check_job", {"job_id": job_id}))

    def run_job(self: "ExecutionEngine", job_submission: dict) -> str:
        return self.simple_call("run_job", job_submission)
