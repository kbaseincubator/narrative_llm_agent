import requests
import uuid
from typing import Any

CONTENT_TYPE = "content-type"
APPLICATION_JSON = "application/json"
RESULT = "result"

class ServerError(Exception):
    def __init__(self: "ServerError", name: str, code: int, message: str, data: Any=None, error=None):
        super(Exception, self).__init__(message)
        self.name = name
        self.code = code
        self.message = '' if message is None else message
        self.data = data or error or ''
        # data = JSON RPC 2.0, error = 1.1

    def __str__(self):
        return self.name + ': ' + str(self.code) + '. ' + self.message + \
            '\n' + self.data

class ServiceClient:
    def __init__(self: "ServiceClient", endpoint: str, service: str, token: str=None, timeout: int=1800):
        self._endpoint = endpoint
        self._service = service
        self._token = token
        self._headers = {}
        if token is not None:
            self._headers["Authorization"] = token
        self._timeout = timeout

    def simple_call(self: "ServiceClient", method: str, params: Any) -> Any:
        return self.make_kbase_jsonrpc_1_call(method, [params])[0]

    def make_kbase_jsonrpc_1_call(
            self: "ServiceClient",
            method: str,
            params: list[Any]) -> Any:
        """
        A very simple JSON-RPC 1 request maker for KBase services.

        If a failure happens, it prints the message from an expected error packet, and
        raises the requests.HTTPError.
        """
        call_id = str(uuid.uuid4())
        json_rpc_package = {
            "params": params,
            "method": f"{self._service}.{method}",
            "version": "1.1",
            "id": call_id
        }
        resp = requests.post(
            self._endpoint,
            json=json_rpc_package,
            headers=self._headers,
            timeout=self._timeout
        )
        if resp.status_code == 500:
            if resp.headers.get(CONTENT_TYPE) == APPLICATION_JSON:
                err = resp.json()
                if "error" in err:
                    raise ServerError(**err["error"])
                else:
                    raise ServerError("Unknown", 0, resp.text)
            else:
                raise ServerError("Unknown", 0, resp.text)

        resp.raise_for_status()
        json_result = resp.json()
        if RESULT not in json_result:
            raise ServerError("Unknown", 0, "An unknown server error occurred")
        return json_result[RESULT]
