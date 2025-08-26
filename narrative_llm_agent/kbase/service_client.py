import requests
import uuid
from typing import Any
from narrative_llm_agent.config import get_kbase_auth_token

CONTENT_TYPE = "content-type"
APPLICATION_JSON = "application/json"
RESULT = "result"


class ServerError(Exception):
    name: str
    code: int
    message: str
    data: Any

    def __init__(
        self: "ServerError", name: str, code: int, message: str, data: Any = None
    ):
        super(Exception, self).__init__(message)
        self.name = name
        self.code = code
        self.message = "" if message is None else message
        self.data = data or ""
        # data = JSON RPC 2.0, error = 1.1

    def __str__(self):
        return (
            self.name + ": " + str(self.code) + ". " + self.message + "\n" + self.data
        )


class ServiceClient:
    def __init__(
        self: "ServiceClient",
        endpoint: str,
        service: str,
        token: str = None,
        timeout: int = 1800,
    ):
        self._endpoint = endpoint
        self._service = service
        self._token = token
        self._headers = {}
        if self._token is None:
            self._token = get_kbase_auth_token()
        if self._token is not None:
            self._headers["Authorization"] = self._token
        self._timeout = timeout

    def simple_call(self: "ServiceClient", method: str, params: Any) -> Any:
        return self.make_kbase_jsonrpc_1_call(f"{self._service}.{method}", [params])[0]

    def make_kbase_jsonrpc_1_call(
        self: "ServiceClient", method: str, params: Any
    ) -> Any:
        """
        A very simple JSON-RPC 1 request maker for KBase services.

        If a failure happens, it prints the message from an expected error packet, and
        raises the requests.HTTPError.
        """
        call_id = str(uuid.uuid4())
        json_rpc_package = {
            "params": params,
            "method": method,
            "version": "1.1",
            "id": call_id,
        }
        resp = requests.post(
            self._endpoint,
            json=json_rpc_package,
            headers=self._headers,
            timeout=self._timeout,
        )
        if resp.status_code == 500:
            error_packet = {}
            if resp.headers.get(CONTENT_TYPE) == APPLICATION_JSON:
                err = resp.json()
                if "error" in err:
                    error_packet = err["error"]
                    if not isinstance(error_packet, dict):
                        error_packet = {"data": err["error"]}
            raise ServerError(
                error_packet.get("name", "Unknown"),
                error_packet.get("code", 0),
                error_packet.get("message", resp.text),
                error_packet.get("data", error_packet.get("error", "")),
            )

        resp.raise_for_status()
        json_result = resp.json()
        if RESULT not in json_result:
            raise ServerError("Unknown", 0, "An unknown server error occurred")
        return json_result[RESULT]
